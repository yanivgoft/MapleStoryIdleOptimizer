# MapleStory Idle RPG — DPS Calculators

A set of per-class Excel DPS calculators for [MapleStory Idle RPG], built from live wiki data and
official patch notes. Pick your class, plug in your stats, and see your steady-state DPS broken
down by skill — plus which stat to invest in next.

## What's here

Twelve class folders, each fully self-contained and independently downloadable:

```
<Class>/
├── <Class>-DPS-Calculator.xlsx   # the workbook itself
└── potential_cubes_ev.py         # standalone Potential Cube EV calculator (see below)
```

| Stat identity | Classes |
|---|---|
| INT-main / LUK-sub | FP-Mage, Ice-Lightning-Mage, Bishop |
| LUK-main / DEX-sub | Night-Lord, Shadower |
| DEX-main / STR-sub | Bowmaster, Marksman, Corsair |
| STR-main / DEX-sub | Hero, Paladin, Dark-Knight, Buccaneer |

Just want one class? Download that one folder — nothing else is needed to use the workbook or
run its cube calculator.

`src/` holds the Python that generates and verifies every workbook (see "Regenerating a workbook"
below) — you don't need it just to *use* a calculator, only to rebuild or modify one.
`data/` holds the two small JSON tables (`factor_table.json`, `cube_potential_data.json`) those
scripts read from.

Each workbook is fully self-contained — open it in Excel (or LibreOffice/Google Sheets), fill in
your own stats, and every other sheet recalculates live.

## Using a workbook

1. Open `<Class>/<Class>-DPS-Calculator.xlsx`.
2. Read the **README** sheet first — it explains this specific class's own modeling decisions and
   any known data gaps for that class.
3. Edit only the **yellow-highlighted cells on the Inputs sheet** — everything else is computed
   and will be overwritten if the workbook is regenerated from source.
4. Check **Summary** for your Total DPS, a per-skill DPS breakdown, and a Marginal DPS & Stat
   Value table (how much DPS you gain per +1 of each stat — use this to decide what to invest in).
5. **Sensitivity** has the full detail behind that marginal-value table, one block per stat.
6. **CubeData / PotentialCubes** model your current gear's Potential Cube lines. For the
   standalone version of that same math — a command-line tool that reads your gear straight out
   of the workbook — grab the prebuilt executable for your OS from the
   **[latest Release](../../releases/latest)** (`potential_cubes_ev-macos` or
   `potential_cubes_ev-windows.exe`), drop it into that class's own folder next to the `.xlsx`,
   and double-click it — no Python required. (On macOS, right-click → Open the first time, since
   it isn't signed by an Apple-registered developer.) If you'd rather run it from source instead,
   `python3 potential_cubes_ev.py` from inside that folder does the same thing (auto-detects the
   one `.xlsx` file next to it); requires `pip install openpyxl formulas`.

### Content Type

`Content Type` on the Inputs sheet picks what you're fighting; `Monster Defense` and `Fixed Fight
Duration` are both computed from it automatically — you no longer set either one by hand (except
PvP's Defense, see below). `Chapter-Stage` (right below Content Type) feeds the chapter- and
dungeon-based types — type it as `28-9` (chapter-substage, e.g. Breakthrough Chapter 28 stage 9)
for the chapter-based types, or just a plain number like `80` for the five Dungeon types (their
own stage number, unrelated to Chapter). For Chapter Boss you can type just the chapter number
alone (e.g. `28`) since it has no sub-stage.

| Content Type | Chapter-Stage format | Monster Defense | Duration |
|---|---|---|---|
| Chapter Boss | `28` (chapter only) | `3200 + 50 × (Chapter − 28)` | 70s |
| Breakthrough | `28-9` | see below | 40s |
| Chapter Hunt | `28-9` | same formula as Breakthrough | steady-state (no duration) |
| Hero Dungeon | `80` (stage only) | `650 + Stage × 50` | 50s |
| World Boss | — | flat `62,100` | 75s |
| Weapon Dungeon | `80` (stage only) | `Stage × 50` | 22s |
| Enhancement Dungeon | `80` (stage only) | `950 + Stage × 50` | 25s |
| EXP Dungeon | `80` (stage only) | `250 + Stage × 50` | 40s |
| Equipment Dungeon | `80` (stage only) | `250 + Stage × 50` | 40s |
| PvP | — | your own Defense stat (assumes the opponent has the same) | own fixed 15s window |

For Breakthrough/Chapter Hunt, the number after the dash is the sub-stage shown in-game (the "9"
in 28-9). Chapters 29–38 have 14 sub-stages each before that chapter's own boss; chapter 39 onward
has 19 sub-stages each. Defense is anchored at the one confirmed data point — 4860 at Chapter 28,
Stage 9 — and increases by 20 for every sub-stage crossed from there, correctly carrying the count
across chapter boundaries. Only that one anchor point is confirmed; everything computed from it is
an extrapolation using the known sub-stage-count pattern, not independently confirmed data.

If none of the above fits your content, or you have a more precise value, `PvP` is the one
Content Type where Monster Defense stays a value you set directly (via the `Defense` input, your
own character's Defense stat) rather than a computed one.

**Boss/Normal Emphasis** (only used when Content Type is Breakthrough or Hero Dungeon, since
those mix boss- and normal-monster kills) is a 5-option dropdown instead of a free-typed
percentage: More Normal (70% normal-weighted) / A Little More Normal (60%, the default) / Equal
(50%) / A Little More Boss (40%) / More Boss (30%).

**Dark Knight and Bishop** track `Defense` and `Defense %` as full stats (not just a PvP estimate)
— Iron Wall and Invincible respectively convert 10% of your total Defense into STR/INT once
unlocked, so these two classes' `Defense`/`Defense %` also have their own Sensitivity marginal-DPS
rows and a `Defense %` PotentialCubes value. Every other class's `Defense` input is used only for
the PvP estimate above and has no other DPS effect.

## Regenerating a workbook from source

Each workbook is generated by a matching Python script in `src/`, so it can be rebuilt or modified
without hand-editing formulas. Run these from the repo root:

```
python3 src/build_<class>_workbook.py      # writes <Class>/<Class>-DPS-Calculator.xlsx
python3 src/verify_<class>_workbook.py     # independently re-derives every DPS number in
                                            # pure Python and checks it against the live
                                            # Excel formulas, cell for cell
```

Requires Python 3 with `openpyxl` and `formulas` installed (`pip install openpyxl formulas`).

Rebuilding preserves your own Inputs and PotentialCubes values from the existing file, so you
won't lose your stats if you regenerate after an update. If you rebuild, remember to re-copy
`src/potential_cubes_ev.py` into that class's folder too — it's a plain copy, not a symlink, so
the two don't auto-sync.

## Credits & data sources

- **[MapleStory Damage Calculator](https://djc-0de.github.io/Maplestory-Damage-Calculator/)** —
  this project's `data/factor_table.json` and `data/cube_potential_data.json` (the level 1→300
  skill-scaling factor table and the Potential Cube line/rate tables) are extracted directly from
  that project's own already-built game-mechanics data. This project exists as a companion to it,
  covering per-class DPS math as standalone Excel workbooks rather than a web UI.
- **[idle.maplestorywiki.net](https://idle.maplestorywiki.net)**, an editable community wiki, is
  the primary source for every skill's damage curve, cooldown, and mastery table used in this
  project. Its own content is published under a
  [Creative Commons Attribution-NonCommercial-ShareAlike](https://creativecommons.org/licenses/by-nc-sa/4.0/)
  license — credit to that wiki's editors for compiling the underlying game data these
  calculators are built from.
- Post-patch numeric deltas (where the wiki lagged behind a game update) are cross-referenced
  against the game's own official in-game patch notes.

Every skill's damage, cooldown, and mastery bonus is sourced from the wiki above and
cross-referenced against those official patch notes. Where a skill has a full per-level curve on
the wiki, that curve is matched exactly (not approximated) against the game's own internal
scaling table. Where it doesn't — a handful of classes were added to the wiki without full
per-skill documentation — the workbook says so explicitly, both in that class's own README sheet
and in **[KNOWN_GAPS.md](KNOWN_GAPS.md)**, which is the single project-wide list of every
assumption or approximation in every class. Nothing is silently guessed; anything uncertain is
labeled as such in the workbook itself.

## Accuracy

Every number in every workbook is independently re-derived in a plain Python script and checked
against the live Excel formulas — not just at your current stats, but across every monster type
(boss/normal/breakthrough/PvP), both fixed-duration and steady-state combat modes, and every
level from 1 to 200, checking specifically that no unlock or mastery threshold ever *decreases*
your DPS. See `KNOWN_GAPS.md` for the handful of places where the underlying game data itself —
not the spreadsheet math — is uncertain.

## Future work

Have a feature you want, a bug you've found, or a class that feels off? Open an issue — feedback
and requests are welcome.

**Next up:** verifying and closing the data gaps in Bishop, Paladin, Buccaneer, and Corsair (see
`KNOWN_GAPS.md` for exactly what's flagged in each) — these four classes have the least complete
wiki data of the twelve and are the current priority.

**Further out:** none of the twelve workbooks model MP consumption, Artifacts, or Companions yet
— these are all planned additions once the class-data gaps above are settled.

