#!/usr/bin/env python3
"""
Computes exact Potential Cubes EV for every equipment slot x potential type, reading current
gear state and live DPS-per-unit conversions straight out of a generated DPS workbook (e.g.
FP-Mage-DPS-Calculator.xlsx / Night-Lord-DPS-Calculator.xlsx / Ice-Lightning-Mage-DPS-Calculator.xlsx).

STANDALONE: this script needs nothing else from this repo — only this one file, a copy of your
own workbook, and `pip install openpyxl formulas numpy`. Everything class-specific (which stats
exist, their DPS-per-unit conversion, rarity upgrade rates/pity caps, your current gear) is read
directly out of the workbook's own CubeData/PotentialCubes/Summary sheets — there is deliberately
no dependency on any build_*_workbook.py module, so this can be handed to someone who only has
the .xlsx file and not the rest of this repo.

Usage:
    python3 potential_cubes_ev.py                          # auto-detects the single .xlsx in cwd
    python3 potential_cubes_ev.py MyClass-DPS-Calculator.xlsx

Run after regenerating/saving the workbook with your real gear filled into the PotentialCubes
sheet. Writes a full milestone breakdown to "<workbook name>_potential_cubes_ev.csv" next to
the workbook.

Methodology
-----------
Every cube fully re-rolls all 3 potential lines, and there's no undo — a cube permanently
overwrites whatever you had. So the right question isn't "will this roll beat my ORIGINAL
gear" — after your first cube, that original value is gone forever, so every decision from then
on should compare against the best you could still expect to achieve by continuing, not against
a value you can no longer return to. That "best you could still achieve" is itself recursive
(it depends on how many cubes you have left, which depends on outcomes of future cubes, ...), so
this is a proper optimal-stopping problem, solved exactly via backward induction:

  1. Per (rarity, slot): the full distribution of one roll's total DPS value, by enumerating
     every (line1, line2, line3) combination (the 3 lines are independent draws) and combining
     each combination's DPS contribution via `combined_dps_gain` — lines on the SAME stat add
     (two 5% Max Damage lines really are one 10% Max Damage bucket), but lines on DIFFERENT stats
     combine multiplicatively (each stat's own marginal DPS-per-unit is exact only holding
     everything else fixed, so two different stats' independent 1% gains compound to
     1.01*1.01-1=2.0201%, not a naive 2%) — see combined_dps_gain's own docstring for the full
     reasoning.
  2. Define W_k(tier, pity) = the expected value of optimal play, GIVEN you are about to use a
     cube while at that (tier, pity) state, with k cubes remaining after this one. Solved via
     backward induction from W_0 = -infinity (no cubes left after this one — forced to accept
     whatever this roll is, since there's no more chances to improve or option to "keep the old
     item" — that option vanished the moment this cube was used):
         W_k(tier, pity) = E over (this cube's tier-upgrade check + roll) of
                            max(roll, W_{k-1}(resulting tier, resulting pity))
     i.e. each cube, you'd rationally keep the roll only if it beats the known optimal value of
     continuing with your remaining cubes — not if it merely beats your original gear.
  3. Your ORIGINAL held value only ever matters once, at the very top: given K total cubes
     available and currently holding `current_value`, the optimal choice is
         V_K = max(current_value, W_K(start_tier, start_pity))
     — i.e. "is it worth using even one cube at all, given optimal play from then on." EV(K) =
     V_K - current_value, which is therefore always >= 0 (you're never forced to make things
     worse — you always retain the option to simply not cube).

Skill Cooldown Decrease lines are the one stat NOT priced as "value x a per-unit rate": CDR's DPS
effect is a step function (fixed-duration fights gain a whole extra cast only when the cooldown
crosses a threshold), so a single "+1 second" test says almost nothing about +2 or +3 seconds. They
are priced from the Sensitivity sheet's "Cooldown Reduction Milestone Sweep" table instead
(interpolating between its 0.5s steps) — see cdr_total_dps()/cdr_factor() below.

This replaces two earlier, less accurate versions: one assumed a free undo across all N cubes
(order statistics / max of N draws), the other used a *fixed* stopping threshold (your original
value) instead of the correct recursive one — which meant it would "settle" for a roll that
barely beat original even when continuing was still clearly worth it. Every input here (roll
distribution, tier-upgrade timing, the backward-induction recursion) is exact — no approximation
or sampling.
"""
import argparse
import csv
import multiprocessing
import re
import sys
from pathlib import Path

import numpy as np
import openpyxl

# Must run before ANY other module-level code: when frozen into a onefile executable
# (PyInstaller), a multiprocessing child re-invokes this same binary as its own "interpreter,"
# re-running this whole module from the top with interpreter-style flags in sys.argv
# (-B -S -I -c ...) that argparse below can't parse. freeze_support() detects that case and
# exits before reaching any of that — but only if called first, before parse_args() etc. run.
multiprocessing.freeze_support()

MAX_CUBES = 1000

# User-specified milestone cube counts for exact EV reporting — class-agnostic, same list for
# every workbook.
CUBE_MILESTONES = [
    5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100,
    125, 150, 175, 200, 250, 300, 400, 500, 1000,
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Computes exact Potential Cubes EV directly from a generated DPS workbook."
    )
    parser.add_argument(
        "xlsx", nargs="?", default=None,
        help="Path to the workbook (e.g. Night-Lord-DPS-Calculator.xlsx). If omitted, "
             "auto-detects the single .xlsx file in the current directory.",
    )
    return parser.parse_args()


def resolve_xlsx_path(arg):
    if arg:
        path = Path(arg)
        if not path.exists():
            sys.exit(f"File not found: {path}")
        return path
    candidates = [
        p for p in Path.cwd().glob("*.xlsx")
        if not p.name.startswith("~$")  # skip Excel lock files
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        sys.exit(
            "No .xlsx file found in the current directory. Pass the workbook path explicitly:\n"
            "  python3 potential_cubes_ev.py MyClass-DPS-Calculator.xlsx"
        )
    sys.exit(
        "Multiple .xlsx files found in the current directory — pass the one to use explicitly:\n"
        + "\n".join(f"  {p.name}" for p in candidates)
    )


args = parse_args()
XLSX_PATH = resolve_xlsx_path(args.xlsx)
CSV_PATH = XLSX_PATH.with_name(f"{XLSX_PATH.stem}_potential_cubes_ev.csv")

# ---------------------------------------------------------------------------
# Load the workbook twice: `openpyxl` for the literal (non-formula) tables — CubeData's
# flattened roll table (A:H, except the live H column), its Rarity/Rate/MaxPity/PotentialType
# table (M:P), and the PotentialCubes current-gear table — and `formulas` (a real Excel formula evaluator)
# for the handful of cells that are genuinely live formulas: CubeData's own "Stat -> DPSPerUnit"
# lookup table (J:K) and the Summary sheet's Total DPS cell, both of which chain back through
# Sensitivity!H's marginal-DPS-per-stat formulas.
# ---------------------------------------------------------------------------
print(f"Loading workbook: {XLSX_PATH}")
_wb = openpyxl.load_workbook(XLSX_PATH, data_only=False)

import formulas  # noqa: E402

xl_model = formulas.ExcelModel().loads(str(XLSX_PATH)).finish()
solution = xl_model.calculate()


def read_formula_raw(sheet, cell):
    suffix = f"{sheet.upper()}'!{cell.upper()}"
    for k, v in solution.items():
        if k.upper().endswith(suffix):
            return np.asarray(v.value).reshape(-1)[0]
    raise KeyError(f"cell not found in workbook: {sheet}!{cell}")


def read_formula_num(sheet, cell):
    return float(read_formula_raw(sheet, cell))


def find_row_by_label(ws, label, column=1, max_row=60):
    """Scans down a column for a cell whose text matches `label` (case-insensitive, stripped)."""
    target = label.strip().lower()
    for row in range(1, max_row + 1):
        value = ws.cell(row=row, column=column).value
        if value is not None and str(value).strip().lower() == target:
            return row
    raise KeyError(f"label {label!r} not found in column {column} (rows 1-{max_row})")


def column_values(ws, column, start_row, stop_on_blank=True):
    """Reads down a column starting at start_row until a blank cell (or the sheet ends)."""
    values = []
    row = start_row
    while True:
        value = ws.cell(row=row, column=column).value
        if stop_on_blank and (value is None or value == ""):
            break
        if value is None and not stop_on_blank:
            break
        values.append(value)
        row += 1
    return values


# ---------------------------------------------------------------------------
# Stat -> DPS-per-unit lookup (CubeData!J:K) — every distinct potential-line stat name mapped to
# its live marginal DPS value. All class-specific special-casing (Main Stat Per Level's live
# level-multiplication, Crit Rate's post-cap fallback to Crit Damage, Companion Summoning's
# not-modeled fallback, etc.) is already baked into this table's own Excel formulas at build
# time — nothing needs to be reimplemented here.
# ---------------------------------------------------------------------------
def load_dps_per_unit_table():
    ws_cube_data = _wb["CubeData"]
    header_row = find_row_by_label(ws_cube_data, "Stat", column=10, max_row=5)
    stats = column_values(ws_cube_data, 10, header_row + 1)
    lookup = {}
    for i, stat in enumerate(stats):
        r = header_row + 1 + i
        lookup[stat] = 0.0 if stat == "(none)" else read_formula_num("CUBEDATA", f"K{r}")
    return lookup


DPS_PER_UNIT = load_dps_per_unit_table()


def dps_per_unit(stat_name):
    return DPS_PER_UNIT.get(stat_name, 0.0)


def find_total_dps():
    ws = _wb["Summary"]
    row = find_row_by_label(ws, "TOTAL DPS", column=1, max_row=40)
    return read_formula_num("SUMMARY", f"B{row}")


# The character's current Total DPS — a single constant for the whole script run, needed by
# combined_dps_gain() below to convert an absolute DPS delta into "how many percentage points of
# my current Total DPS is this," which is what the group-then-multiply combining math actually
# operates on (see combined_dps_gain's own docstring).
BASELINE_DPS = find_total_dps()


# ---------------------------------------------------------------------------
# Skill Cooldown Decrease — priced from the Sensitivity sheet's "Cooldown Reduction Milestone
# Sweep" table (absolute CDR seconds -> full-model Total DPS), NOT from CubeData's single
# DPS-per-unit rate. That rate is the gain from one "+1 second" test, and CDR is a step function in
# fixed-duration content: the same workbook can show ~1% for +1s but ~3.4% for +2s and ~5.8% for
# +3s, so scaling the +1s gain linearly badly under-values bigger CDR rolls.
#
# The table is in ABSOLUTE seconds and your Inputs CDR (CDR_CURRENT) already includes whatever CDR
# lines are rolled on gear right now, so a roll's value is always evaluated against a per-row
# baseline: your total CDR minus the CDR on that row's own current lines (see row_cdr_baseline).
# ---------------------------------------------------------------------------
CDR_STAT = "Skill Cooldown Decrease (seconds)"
CDR_INPUT_ROW = None
_CDR_NOTES = set()
_CDR_EXACT_FAILED = set()


def load_cdr_curve():
    ws = _wb["Sensitivity"]
    try:
        stat_row = find_row_by_label(ws, CDR_STAT, column=1, max_row=150)
        current = read_formula_num("SENSITIVITY", f"D{stat_row}")  # "Current Value" column of the Stat table
        # "Current Value" is a formula like =Inputs!$B$32 — remember that cell so the model can be re-evaluated
        # at another CDR value if a baseline ever falls below the table's first step (see exact_total_at_cdr).
        match = re.search(r"Inputs!\$?B\$?(\d+)", str(ws.cell(row=stat_row, column=4).value))
        global CDR_INPUT_ROW
        CDR_INPUT_ROW = int(match.group(1)) if match else None
    except KeyError:
        return 0.0, None
    title_row = None
    for row in range(1, ws.max_row + 1):
        value = ws.cell(row=row, column=1).value
        if isinstance(value, str) and value.startswith("Cooldown Reduction Milestone Sweep"):
            title_row = row
            break
    if title_row is None:
        return current, None
    points = {}
    row = title_row + 2  # title, then the header row, then one row per swept CDR value
    while True:
        cdr = ws.cell(row=row, column=1).value
        if not isinstance(cdr, (int, float)):
            break
        points[float(cdr)] = read_formula_num("SENSITIVITY", f"B{row}")
        row += 1
    if not points:
        return current, None
    points[float(current)] = BASELINE_DPS  # the live model state is exact, wherever it falls on the grid
    return current, sorted(points.items())


CDR_CURRENT, CDR_POINTS = load_cdr_curve()


def exact_total_at_cdr(cdr):
    """Re-evaluates the whole model with Inputs' Skill Cooldown Decrease set to `cdr` and returns Total DPS
    (None if that can't be done). Only needed when a row's CDR baseline is BELOW the table's first step
    (0.5s) — i.e. you already have CDR in Inputs and one row holds all of it, so its baseline is 0s — which
    the table can't answer. Takes about as long as the initial workbook load, and runs at most once per value."""
    if CDR_INPUT_ROW is None or cdr in _CDR_EXACT_FAILED:
        return None
    _CDR_EXACT_FAILED.add(cdr)  # cleared again on success below, so a failure is only ever attempted once
    try:
        print(f"  (re-evaluating the workbook once at {cdr:g}s of Skill Cooldown Decrease — the table starts at 0.5s)")
        cell = f"'[{XLSX_PATH.name}]INPUTS'!B{CDR_INPUT_ROW}"
        sol = xl_model.calculate(inputs={cell: cdr})
        total_row = find_row_by_label(_wb["Summary"], "TOTAL DPS", column=1, max_row=40)
        suffix = f"SUMMARY'!B{total_row}"
        for k, v in sol.items():
            if k.upper().endswith(suffix):
                _CDR_EXACT_FAILED.discard(cdr)
                return float(np.asarray(v.value).reshape(-1)[0])
    except Exception as exc:  # fall back to the +1s rate rather than failing the whole run
        print(f"  (couldn't re-evaluate the workbook at {cdr:g}s of CDR: {exc})")
    return None


def cdr_total_dps(cdr):
    """Total DPS at a given TOTAL Skill Cooldown Decrease: piecewise-linear through the table's points.
    Beyond the table's top step the last segment's slope continues. Below its first point (only reachable
    when your current CDR is above 0 and one row holds all of it) the model is re-evaluated at that CDR
    once (exact_total_at_cdr); if that fails, the old +1s rate is used."""
    xs = [x for x, _ in CDR_POINTS]
    if cdr < xs[0] and not any(abs(cdr - x) < 1e-9 for x in xs):
        exact = exact_total_at_cdr(cdr)
        if exact is not None:
            CDR_POINTS.append((float(cdr), exact))
            CDR_POINTS.sort()
            return cdr_total_dps(cdr)
    if cdr <= xs[0]:
        if cdr < xs[0]:
            _CDR_NOTES.add("below")
        return max(0.0, CDR_POINTS[0][1] - (xs[0] - cdr) * DPS_PER_UNIT.get(CDR_STAT, 0.0))
    if cdr >= xs[-1]:
        if cdr > xs[-1]:
            _CDR_NOTES.add("above")
        (x0, t0), (x1, t1) = CDR_POINTS[-2], CDR_POINTS[-1]
        return t1 + (cdr - x1) * max(0.0, (t1 - t0) / (x1 - x0))
    import bisect
    i = bisect.bisect_right(xs, cdr)
    (x0, t0), (x1, t1) = CDR_POINTS[i - 1], CDR_POINTS[i]
    return t0 + (t1 - t0) * (cdr - x0) / (x1 - x0)


def cdr_factor(extra_cdr, baseline_cdr):
    """Multiplicative DPS factor from `extra_cdr` seconds of CDR on top of `baseline_cdr` seconds."""
    if CDR_POINTS is None:  # workbook without the milestone table: fall back to the linear +1s rate
        return 1.0 + extra_cdr * DPS_PER_UNIT.get(CDR_STAT, 0.0) / BASELINE_DPS
    base = cdr_total_dps(baseline_cdr)
    return cdr_total_dps(baseline_cdr + extra_cdr) / base if base > 0 else 1.0


def row_cdr_baseline(state):
    """Total CDR the character would have WITHOUT this row's own current CDR lines."""
    own = sum(v for stat, v in state["lines"] if stat == CDR_STAT)
    if own > CDR_CURRENT + 1e-9:
        print(
            f"  note: {state['slot']} / {state['potential_type']} lists {own:g}s of Skill Cooldown Decrease but your "
            f"Inputs CDR is only {CDR_CURRENT:g}s — treating the rest of your CDR as 0."
        )
    return max(0.0, CDR_CURRENT - own)


def combined_dps_gain(stat_value_pairs, cdr_baseline=None):
    """Combines multiple (stat, raw_value) lines into one true DPS-Gain number, instead of the
    naive `sum(value*dps_per_unit(stat) for ...)` this project used everywhere until now.

    Two lines of the SAME stat are correctly additive before any DPS math happens at all — two 5%
    Max Damage lines really are just one 10% Max Damage bucket, so their combined DPS effect is
    exactly double a single 5% line's effect, not more. But two DIFFERENT stats, each independently
    worth (say) 1% DPS on its own, do NOT simply add to 2% when both are applied together — they
    live in different multiplicative buckets of the damage formula, so the true combined effect is
    `1.01 * 1.01 - 1 = 2.0201%`, not `2%`. The naive sum silently drops that second-order
    cross-term (small for small individual gains, but growing for larger ones).

    Implementation: group by stat first (sum raw values within a group, so same-stat lines combine
    additively as they should), convert each DISTINCT stat's grouped value to a DPS-Gain via its
    own dps_per_unit rate, express that as a multiplicative factor relative to BASELINE_DPS, then
    take the product of all distinct stats' factors — exactly the "1.01 * 1.01" shape above,
    generalized to any number of distinct stats. Returns an absolute DPS delta (same units as the
    old naive sum), so every caller downstream is unaffected by this change in how it's computed.

    Skill Cooldown Decrease is the exception to "value x per-unit rate": its group's factor comes from
    cdr_factor() (the Sensitivity sheet's CDR table), evaluated on top of `cdr_baseline` seconds of CDR
    (defaults to your whole current CDR; per-row callers pass row_cdr_baseline()).
    """
    grouped = {}
    for stat, value in stat_value_pairs:
        if not stat or stat == "(none)":
            continue
        grouped[stat] = grouped.get(stat, 0.0) + value
    factor = 1.0
    for stat, total_value in grouped.items():
        if stat == CDR_STAT:
            factor *= cdr_factor(total_value, CDR_CURRENT if cdr_baseline is None else cdr_baseline)
        else:
            factor *= 1.0 + (total_value * dps_per_unit(stat)) / BASELINE_DPS
    return BASELINE_DPS * (factor - 1.0)


# ---------------------------------------------------------------------------
# Rarity order + upgrade rates/pity caps (CubeData!M:P) — literal values, no live formulas.
# Potential and Bonus Potential have different pity caps (confirmed by the user), so this table
# is keyed by potential type first, then rarity: RARITY_UPGRADE_RATES[potential_type][rarity].
# ---------------------------------------------------------------------------
def load_rarity_table():
    ws_cube_data = _wb["CubeData"]
    header_row = find_row_by_label(ws_cube_data, "Rarity", column=13, max_row=5)
    order = []
    rates = {}
    row = header_row + 1
    while True:
        rarity = ws_cube_data.cell(row=row, column=13).value
        if rarity is None or rarity == "":
            break
        potential_type = ws_cube_data.cell(row=row, column=16).value
        rates.setdefault(potential_type, {})[rarity] = dict(
            rate=float(ws_cube_data.cell(row=row, column=14).value),
            max=float(ws_cube_data.cell(row=row, column=15).value),
        )
        if rarity not in order:
            order.append(rarity)
        row += 1
    return order, rates


RARITY_ORDER, RARITY_UPGRADE_RATES = load_rarity_table()


# ---------------------------------------------------------------------------
# Flattened per-(slot, rarity, line) roll table (CubeData!A:G — value/weight/prime). Stores the
# raw (stat, value) pair rather than pre-converting to a DPS number — roll_distribution() needs
# the stat identity preserved so it can correctly group same-stat lines before applying
# combined_dps_gain()'s multiplicative combining across different stats.
# ---------------------------------------------------------------------------
def load_roll_table():
    ws_cube_data = _wb["CubeData"]
    header_row = find_row_by_label(ws_cube_data, "Slot", column=1, max_row=5)
    table = {}  # (slot, rarity, line_num) -> list of (stat, value, weight)
    row = header_row + 1
    while True:
        slot = ws_cube_data.cell(row=row, column=1).value
        if slot is None or slot == "":
            break
        rarity = ws_cube_data.cell(row=row, column=2).value
        line_num = int(ws_cube_data.cell(row=row, column=3).value)
        stat = ws_cube_data.cell(row=row, column=4).value
        value = float(ws_cube_data.cell(row=row, column=5).value)
        weight = float(ws_cube_data.cell(row=row, column=6).value)
        key = (slot, rarity, line_num)
        table.setdefault(key, []).append((stat, value, weight))
        row += 1
    return table


ROLL_TABLE = load_roll_table()


# ---------------------------------------------------------------------------
# Current gear state (PotentialCubes sheet) — literal values, no live formulas.
# ---------------------------------------------------------------------------
def read_current_state():
    ws = _wb["PotentialCubes"]
    header_row = find_row_by_label(ws, "Slot", column=1, max_row=10)
    rows = []
    row = header_row + 1
    while True:
        slot = ws.cell(row=row, column=1).value
        if slot is None or slot == "":
            break
        lines = []
        for stat_col, val_col in ((5, 6), (7, 8), (9, 10)):
            stat = ws.cell(row=row, column=stat_col).value
            val = ws.cell(row=row, column=val_col).value
            lines.append((stat if stat is not None else "(none)", float(val) if val is not None else 0.0))
        rows.append(dict(
            slot=slot,
            potential_type=ws.cell(row=row, column=2).value,
            rarity=ws.cell(row=row, column=3).value,
            pity=float(ws.cell(row=row, column=4).value or 0),
            lines=lines,
        ))
        row += 1
    return rows


def current_dps_value(lines, cdr_baseline=None):
    return combined_dps_gain(lines, cdr_baseline)


# ---------------------------------------------------------------------------
# Step 1: exact per-roll distribution at a given (rarity, slot) — full line1 x line2 x line3
# enumeration, collapsed by identical combined DPS-Gain value (via combined_dps_gain, so two lines
# landing on the same stat correctly group/sum before any two DIFFERENT stats' lines are combined
# multiplicatively).
# ---------------------------------------------------------------------------
_roll_dist_cache = {}


def roll_distribution(rarity, slot, cdr_baseline=None):
    # Rows with different CDR baselines (see row_cdr_baseline) price a CDR roll differently, so the
    # baseline is part of the cache key; rows without CDR lines all share one entry.
    cache_key = (rarity, slot, None if cdr_baseline is None else round(cdr_baseline, 6))
    if cache_key in _roll_dist_cache:
        return _roll_dist_cache[cache_key]

    per_line = []
    for line_num in (1, 2, 3):
        # CubeData stores a shared "ALL" generic pool (applies to every slot) plus a small
        # per-slot addition block under the slot's own literal name (only for slots with genuine
        # slot-specific rolls, e.g. eye-accessory/pocket/ring2/face/earrings — most slots still
        # get their own small block, confirmed empirically: every one of the 15 CUBE_SLOTS has
        # *some* rows beyond "ALL"). Both must be merged — "ALL" is never a substitute.
        entries = list(ROLL_TABLE.get(("ALL", rarity, line_num), []))
        entries += ROLL_TABLE.get((slot, rarity, line_num), [])
        total_weight = sum(w for _, _, w in entries)
        per_line.append([(stat, v, w / total_weight) for stat, v, w in entries])

    combos = {}
    for stat1, v1, p1 in per_line[0]:
        for stat2, v2, p2 in per_line[1]:
            for stat3, v3, p3 in per_line[2]:
                v = combined_dps_gain([(stat1, v1), (stat2, v2), (stat3, v3)], cdr_baseline)
                combos[v] = combos.get(v, 0.0) + p1 * p2 * p3

    values = np.array(sorted(combos))
    cdf = np.cumsum(np.array([combos[v] for v in values]))
    cdf[-1] = 1.0  # guard against float drift so F(v) is exactly 1 at the top of the support
    result = (values, cdf)
    _roll_dist_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Step 2 helpers: vectorized E[max(roll, c)] for a whole array of thresholds `c` at once, given
# a tier's roll distribution — via precomputed suffix sums (classic tail-expectation trick).
# ---------------------------------------------------------------------------
def _tail_sums(values, probs):
    """tail_prob[i] = P(roll >= values[i]), tail_exp[i] = E[roll * 1{roll >= values[i]}], with a
    trailing zero appended so index len(values) ("c is above every possible roll") contributes
    nothing — i.e. E[max(roll, c)] = c exactly when c dominates the whole distribution."""
    tail_prob = np.concatenate([np.cumsum(probs[::-1])[::-1], [0.0]])
    tail_exp = np.concatenate([np.cumsum((values * probs)[::-1])[::-1], [0.0]])
    return tail_prob, tail_exp


def _expected_max_with_threshold(values, tail_prob, tail_exp, c):
    idx = np.searchsorted(values, c, side="right")
    surv_prob = tail_prob[idx]
    surv_exp = tail_exp[idx]
    # c=-inf is the k=0 base case ("no continuation possible, forced to accept this roll") —
    # E[max(roll,-inf)] = E[roll] exactly (surv_exp when idx=0), but the algebraic simplification
    # c + (surv_exp - c*surv_prob) hits -inf + inf = NaN there, so it's special-cased directly.
    with np.errstate(invalid="ignore"):
        general = c + (surv_exp - c * surv_prob)
    return np.where(np.isneginf(c), surv_exp, general)


# ---------------------------------------------------------------------------
# Steps 2-3: the optimal-stopping value function W_k(tier, pity), solved by backward induction
# over k = 1..max_cubes. Each cube, the population at (tier, pity) either upgrades (capped-
# geometric pity mechanic, same math as the arrival-time model used elsewhere in this project)
# or stays, then rolls at whichever tier is now active; W_k combines that roll with the known
# optimal value of continuing with k-1 cubes left via E[max(roll, W_{k-1})]. A terminal tier
# (mystic, or any tier with no further upgrade) has no pity dimension, so its state is a single
# scalar rather than a per-pity-bucket array.
# ---------------------------------------------------------------------------
def optimal_stopping_trace(start_rarity, start_pity, slot, current_value, potential_type, max_cubes=MAX_CUBES, cdr_baseline=None):
    rates = RARITY_UPGRADE_RATES[potential_type]
    idx0 = RARITY_ORDER.index(start_rarity)
    tiers = RARITY_ORDER[idx0:]
    dist = {}
    for t in tiers:
        values, cdf = roll_distribution(t, slot, cdr_baseline)
        probs = np.diff(np.concatenate([[0.0], cdf]))
        dist[t] = (values, *_tail_sums(values, probs))

    start_bucket = int(start_pity)
    W_prev = {t: np.full(max(int(rates[t]["max"]), 1), -np.inf) for t in tiers}

    trace = np.empty(max_cubes + 1)
    trace[0] = current_value  # 0 cubes used: still holding the original value, by definition
    for k in range(1, max_cubes + 1):
        W_cur = {}
        for ti, t in enumerate(tiers):
            values, tail_prob, tail_exp = dist[t]
            is_terminal = (ti == len(tiers) - 1) or rates[t]["max"] <= 0
            if is_terminal:
                W_cur[t] = _expected_max_with_threshold(values, tail_prob, tail_exp, W_prev[t])
                continue
            rate = rates[t]["rate"]
            max_pity = int(rates[t]["max"])
            nxt = tiers[ti + 1]
            n = len(W_prev[t])
            idxs = np.arange(n)
            prob_upgrade = np.where(idxs + 1 >= max_pity, 1.0, rate)

            # Stay branch: reroll at tier t; continuation value is W_prev[t] shifted forward one
            # pity bucket (the last bucket's "stay" placeholder is never used — prob_upgrade=1
            # there, since that bucket is exactly the forced-pity cap).
            c_stay = np.empty(n)
            c_stay[:-1] = W_prev[t][1:]
            c_stay[-1] = -np.inf
            e_stay = _expected_max_with_threshold(values, tail_prob, tail_exp, c_stay)

            # Upgrade branch: reroll at the NEW tier this same cube; continuation value is a
            # single scalar (the next tier's pity always resets to 0 on a fresh upgrade).
            values_n, tail_prob_n, tail_exp_n = dist[nxt]
            c_up = W_prev[nxt][0:1]
            e_up = _expected_max_with_threshold(values_n, tail_prob_n, tail_exp_n, c_up)[0]

            W_cur[t] = (1 - prob_upgrade) * e_stay + prob_upgrade * e_up
        W_prev = W_cur
        trace[k] = max(current_value, W_prev[start_rarity][start_bucket])

    return trace


def smallest_n_positive(trace, current_value):
    """First cube count where EV turns positive — well-defined since the optimal-stopping value
    is non-decreasing in the cube budget (more cubes can only give the *option*, never the
    requirement, to do better)."""
    positive = np.flatnonzero(trace[1:] > current_value)
    return int(positive[0]) + 1 if positive.size else None


# ---------------------------------------------------------------------------
# "P(at least one roll beats current within N cubes)" — a plain probability question, no
# weighting by how much better, unlike the EV model above. Same absorbing-chain structure as the
# optimal-stopping trace (tier-upgrade timing is unaffected by roll outcomes, so it's exact), but
# every cube's roll is checked against the ORIGINAL current_value directly (not a recursive
# continuation value), since the question here is just "did I ever beat what I started with."
# ---------------------------------------------------------------------------
def roll_beat_probability(rarity, slot, current_value, cdr_baseline=None):
    values, cdf = roll_distribution(rarity, slot, cdr_baseline)
    idx = np.searchsorted(values, current_value, side="right") - 1
    f = cdf[idx] if idx >= 0 else 0.0
    return 1.0 - f


def probability_any_better_roll(start_rarity, start_pity, slot, current_value, potential_type, max_cubes=MAX_CUBES, cdr_baseline=None):
    rates = RARITY_UPGRADE_RATES[potential_type]
    idx0 = RARITY_ORDER.index(start_rarity)
    tiers = RARITY_ORDER[idx0:]
    p = {t: roll_beat_probability(t, slot, current_value, cdr_baseline) for t in tiers}
    surv = {t: np.zeros(max(int(rates[t]["max"]), 1)) for t in tiers}
    surv[start_rarity][int(start_pity)] = 1.0

    prob_any = np.zeros(max_cubes + 1)
    for k in range(1, max_cubes + 1):
        new_surv = {t: np.zeros_like(surv[t]) for t in tiers}
        for ti, t in enumerate(tiers):
            arr = surv[t]
            is_terminal = (ti == len(tiers) - 1) or rates[t]["max"] <= 0
            if is_terminal:
                new_surv[t][0] += float(arr.sum()) * (1 - p[t])
                continue
            rate = rates[t]["rate"]
            max_pity = int(rates[t]["max"])
            nxt = tiers[ti + 1]
            n = len(arr)
            idxs = np.arange(n)
            prob_upgrade = np.where(idxs + 1 >= max_pity, 1.0, rate)
            stay_mass = arr * (1 - prob_upgrade)
            upgrade_mass = arr * prob_upgrade
            new_surv[t][1:] += (stay_mass * (1 - p[t]))[:-1]
            new_surv[nxt][0] += float(np.sum(upgrade_mass * (1 - p[nxt])))
        surv = new_surv
        prob_any[k] = 1.0 - sum(float(a.sum()) for a in surv.values())
    return prob_any


def smallest_n_for_probability(prob_any, threshold):
    idx = np.flatnonzero(prob_any[1:] >= threshold)
    return int(idx[0]) + 1 if idx.size else None


# ---------------------------------------------------------------------------
# Run for every (slot, potential type) row in the workbook's PotentialCubes sheet.
# ---------------------------------------------------------------------------


def main():
    baseline_dps = BASELINE_DPS
    if CDR_POINTS is not None:
        print(f"Skill Cooldown Decrease is priced from the Sensitivity CDR table (your current CDR: {CDR_CURRENT:g}s):")
        print("  " + "  ".join(f"{x:g}s: {t / baseline_dps * 100 - 100:+.2f}%" for x, t in CDR_POINTS if x != CDR_CURRENT))
    rows = read_current_state()
    results = []
    for state in rows:
        cdr_base = row_cdr_baseline(state)
        cur_val = current_dps_value(state["lines"], cdr_base)
        trace = optimal_stopping_trace(state["rarity"], state["pity"], state["slot"], cur_val, state["potential_type"], cdr_baseline=cdr_base)
        milestone_ev = {
            n: trace[n] - cur_val
            for n in CUBE_MILESTONES
        }
        smallest_n = smallest_n_positive(trace, cur_val)
        prob_any = probability_any_better_roll(state["rarity"], state["pity"], state["slot"], cur_val, state["potential_type"], cdr_baseline=cdr_base)
        n_for_50pct = smallest_n_for_probability(prob_any, 0.5)
        n_for_75pct = smallest_n_for_probability(prob_any, 0.75)
        results.append(dict(
            state, current_value=cur_val, milestone_ev=milestone_ev, smallest_n=smallest_n,
            n_for_50pct=n_for_50pct, n_for_75pct=n_for_75pct,
        ))

    # Regular Potential rows first, then Bonus Potential — sorted within each group by smallest
    # N+ ascending (best opportunities first); rows that never turn positive within 1000 cubes
    # sort last within their group.
    potential_type_order = {"Potential": 0, "Bonus Potential": 1}
    results.sort(key=lambda r: (
        potential_type_order.get(r["potential_type"], 2),
        r["smallest_n"] if r["smallest_n"] is not None else float("inf"),
    ))

    def pct(dps):
        return dps / baseline_dps * 100

    def n_str(n):
        return "never<=1000" if n is None else str(n)

    header = (
        f"{'Slot':14s} {'CurrentGain%':>13s} {'EV@50':>10s} {'EV@200':>10s} "
        f"{'EV@500':>10s} {'MinForPositiveEV':>17s} {'MinFor50%ToImprove':>19s} {'MinFor75%ToImprove':>19s}"
    )
    print()
    print(f"(DPS% columns are expected DPS gain as a percentage of your current Total DPS, {baseline_dps:,.0f})")
    print("(CurrentGain% = the DPS gain your CURRENTLY-rolled value on this line already provides)")
    print("(EV@N = expected additional DPS gain if you optimally reroll this line with N cubes,")
    print(" banking the best result seen along the way and stopping once it's good enough)")
    print("(MinForPositiveEV = fewest cubes where rerolling is expected, on average, to beat keeping your current roll)")
    print("(MinFor50%/75%ToImprove = fewest cubes needed for that % chance that AT LEAST ONE reroll beats your")
    print(" current value — a plain probability of any improvement, not weighted by how much better)")
    print(header)
    print("-" * len(header))
    prev_type = None
    for r in results:
        if r["potential_type"] != prev_type:
            if prev_type is not None:
                print()
            print(f"-- {r['potential_type']} --")
            prev_type = r["potential_type"]
        print(
            f"{r['slot']:14s} {pct(r['current_value']):12.3f}% {pct(r['milestone_ev'][50]):9.3f}% "
            f"{pct(r['milestone_ev'][200]):9.3f}% {pct(r['milestone_ev'][500]):9.3f}% "
            f"{n_str(r['smallest_n']):>17s} {n_str(r['n_for_50pct']):>19s} {n_str(r['n_for_75pct']):>19s}"
        )

    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["Slot", "PotentialType", "Rarity", "Pity", "CurrentValue", "CurrentValue%", "SmallestNPositive", "NFor50PctChance", "NFor75PctChance"]
            + [f"EV@{n}" for n in CUBE_MILESTONES] + [f"EV%@{n}" for n in CUBE_MILESTONES]
        )
        for r in results:
            writer.writerow(
                [r["slot"], r["potential_type"], r["rarity"], r["pity"], r["current_value"], pct(r["current_value"]),
                 r["smallest_n"], r["n_for_50pct"], r["n_for_75pct"]]
                + [r["milestone_ev"][n] for n in CUBE_MILESTONES]
                + [pct(r["milestone_ev"][n]) for n in CUBE_MILESTONES]
            )
    print(f"\nFull 24-milestone breakdown (absolute DPS + % gain) written to {CSV_PATH}")
    if "above" in _CDR_NOTES:
        print("note: some Skill Cooldown Decrease totals exceed the CDR table's top step; its last segment's slope was extended.")
    if "below" in _CDR_NOTES:
        print("note: some Skill Cooldown Decrease baselines fell below the CDR table's first step; the +1s rate was used there.")


if __name__ == "__main__":
    main()
