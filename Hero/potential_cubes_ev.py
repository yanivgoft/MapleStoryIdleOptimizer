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
     every (line1, line2, line3) combination (the 3 lines are independent draws) and summing
     each combination's DPS contribution (value x DPS-per-unit, read from the workbook).
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
# flattened roll table (A:H, except the live H column), its Rarity/Rate/MaxPity table (M:O),
# and the PotentialCubes current-gear table — and `formulas` (a real Excel formula evaluator)
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


# ---------------------------------------------------------------------------
# Rarity order + upgrade rates/pity caps (CubeData!M:O) — literal values, no live formulas.
# ---------------------------------------------------------------------------
def load_rarity_table():
    ws_cube_data = _wb["CubeData"]
    header_row = find_row_by_label(ws_cube_data, "Rarity", column=13, max_row=5)
    order, rates = [], {}
    row = header_row + 1
    while True:
        rarity = ws_cube_data.cell(row=row, column=13).value
        if rarity is None or rarity == "":
            break
        rates[rarity] = dict(
            rate=float(ws_cube_data.cell(row=row, column=14).value),
            max=float(ws_cube_data.cell(row=row, column=15).value),
        )
        order.append(rarity)
        row += 1
    return order, rates


RARITY_ORDER, RARITY_UPGRADE_RATES = load_rarity_table()


# ---------------------------------------------------------------------------
# Flattened per-(slot, rarity, line) roll table (CubeData!A:G — value/weight/prime; DPSPerUnit
# is recomputed here from the Stat->DPSPerUnit table above rather than re-read from CubeData!H,
# since they're guaranteed identical for a given stat name and this avoids one `formulas` lookup
# per row).
# ---------------------------------------------------------------------------
def load_roll_table():
    ws_cube_data = _wb["CubeData"]
    header_row = find_row_by_label(ws_cube_data, "Slot", column=1, max_row=5)
    table = {}  # (slot, rarity, line_num) -> list of (value_dps, weight)
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
        table.setdefault(key, []).append((value * dps_per_unit(stat), weight))
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


def current_dps_value(lines):
    return sum(val * dps_per_unit(stat) for stat, val in lines if stat and stat != "(none)")


# ---------------------------------------------------------------------------
# Step 1: exact per-roll distribution at a given (rarity, slot) — full line1 x line2 x line3
# enumeration, collapsed by identical total value.
# ---------------------------------------------------------------------------
_roll_dist_cache = {}


def roll_distribution(rarity, slot):
    cache_key = (rarity, slot)
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
        total_weight = sum(w for _, w in entries)
        per_line.append([(v, w / total_weight) for v, w in entries])

    combos = {}
    for v1, p1 in per_line[0]:
        for v2, p2 in per_line[1]:
            for v3, p3 in per_line[2]:
                v = v1 + v2 + v3
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
def optimal_stopping_trace(start_rarity, start_pity, slot, current_value, max_cubes=MAX_CUBES):
    idx0 = RARITY_ORDER.index(start_rarity)
    tiers = RARITY_ORDER[idx0:]
    dist = {}
    for t in tiers:
        values, cdf = roll_distribution(t, slot)
        probs = np.diff(np.concatenate([[0.0], cdf]))
        dist[t] = (values, *_tail_sums(values, probs))

    start_bucket = int(start_pity)
    W_prev = {t: np.full(max(int(RARITY_UPGRADE_RATES[t]["max"]), 1), -np.inf) for t in tiers}

    trace = np.empty(max_cubes + 1)
    trace[0] = current_value  # 0 cubes used: still holding the original value, by definition
    for k in range(1, max_cubes + 1):
        W_cur = {}
        for ti, t in enumerate(tiers):
            values, tail_prob, tail_exp = dist[t]
            is_terminal = (ti == len(tiers) - 1) or RARITY_UPGRADE_RATES[t]["max"] <= 0
            if is_terminal:
                W_cur[t] = _expected_max_with_threshold(values, tail_prob, tail_exp, W_prev[t])
                continue
            rate = RARITY_UPGRADE_RATES[t]["rate"]
            max_pity = int(RARITY_UPGRADE_RATES[t]["max"])
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
def roll_beat_probability(rarity, slot, current_value):
    values, cdf = roll_distribution(rarity, slot)
    idx = np.searchsorted(values, current_value, side="right") - 1
    f = cdf[idx] if idx >= 0 else 0.0
    return 1.0 - f


def probability_any_better_roll(start_rarity, start_pity, slot, current_value, max_cubes=MAX_CUBES):
    idx0 = RARITY_ORDER.index(start_rarity)
    tiers = RARITY_ORDER[idx0:]
    p = {t: roll_beat_probability(t, slot, current_value) for t in tiers}
    surv = {t: np.zeros(max(int(RARITY_UPGRADE_RATES[t]["max"]), 1)) for t in tiers}
    surv[start_rarity][int(start_pity)] = 1.0

    prob_any = np.zeros(max_cubes + 1)
    for k in range(1, max_cubes + 1):
        new_surv = {t: np.zeros_like(surv[t]) for t in tiers}
        for ti, t in enumerate(tiers):
            arr = surv[t]
            is_terminal = (ti == len(tiers) - 1) or RARITY_UPGRADE_RATES[t]["max"] <= 0
            if is_terminal:
                new_surv[t][0] += float(arr.sum()) * (1 - p[t])
                continue
            rate = RARITY_UPGRADE_RATES[t]["rate"]
            max_pity = int(RARITY_UPGRADE_RATES[t]["max"])
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
def find_total_dps():
    ws = _wb["Summary"]
    row = find_row_by_label(ws, "TOTAL DPS", column=1, max_row=40)
    return read_formula_num("SUMMARY", f"B{row}")


def main():
    baseline_dps = find_total_dps()
    rows = read_current_state()
    results = []
    for state in rows:
        cur_val = current_dps_value(state["lines"])
        trace = optimal_stopping_trace(state["rarity"], state["pity"], state["slot"], cur_val)
        milestone_ev = {
            n: trace[n] - cur_val
            for n in CUBE_MILESTONES
        }
        smallest_n = smallest_n_positive(trace, cur_val)
        prob_any = probability_any_better_roll(state["rarity"], state["pity"], state["slot"], cur_val)
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


if __name__ == "__main__":
    main()
