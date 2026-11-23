"""Class-agnostic comparison of ``engine.sensitivity`` against a workbook golden file (the numbers of ``sens_reference_generic.py``).

``compare_case(class_module, cid, case, rtol)`` -> (number of values compared, [(name, workbook value, engine value), ...]) - the logic of
the former FP-Mage copy (rel 1e-9 everywhere; the workbook's fractional-window artifact of the companion chain gets ``FRAC_RTOL`` / ``FRAC_ATOL``, see below)
for any class.  Used by ``test_sensitivity.py`` (through ``sens_test_common.SensTest``) for every class, FP-Mage included.

Compared per case: the workbook's Summary baselines (Total / boss-only / normal-only); per stat the Sensitivity table row (Units per +1%, Current, New, Baseline,
New Total, DPS Gain, % Gain) and the block's own Total / boss-only / normal-only; per equip toggle the staging row (DPS Gain, % Gain, unlocked) and the block
totals; the CDR milestone table; the Companion Comparison table (gain, % gain, unlocked, rank) and the Summoning-Time breakdown table.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from engine import sensitivity  # noqa: E402

# Workbook numerics: the companion chain's elementwise MIN is written (a+b-ABS(a-b))/2 and a permanent kit effect has the 1e9 "NEVER" sentinel as one operand,
# which loses ~5e-8 absolute of the other operand in double precision.  For a window of whole seconds (D = 30 s, 45 s ...) that is exact, for a FRACTIONAL
# window (summoning time +1% -> 30.3 s, any non-integer increase) a permanent buff's uptime reads 1 - 1.57e-9 in the workbook instead of 1 (verified cell by cell).
# The engine (like src/companion_python_model.py) computes the exact value, so every companion quantity at a fractional window differs from the workbook by up
# to ~2e-9 relative; a DPS GAIN (a small difference of two totals) inherits an absolute error of ~1e-9 x Total.
FRAC_RTOL = 5e-9
FRAC_ATOL = 2e-9          # x Total DPS, on gains
# sweeps / toggles that put a FRACTIONAL amount into the summoning window (see above); the same for every class
FRAC_STATS = ("companion_summon_time_increase_pct",)
FRAC_TOGGLES = ("arwens_glass_shoes",)


def close(a, b, rtol, atol=0.0):
    if a == b:
        return True
    if a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return a == b
    return abs(a - b) <= rtol * max(abs(a), abs(b)) + atol


def engine_inputs(case):
    d = dict(case["inputs"])
    d["artifact_potential_gain"] = dict(case.get("potential") or {})
    return d


def compare_case(class_module, cid, case, rtol):
    wb = case["workbook"]
    inputs = engine_inputs(case)
    inc = inputs.get("companion_summon_time_increase_pct") or 0
    frac_case = (inc % 1 != 0)          # the baseline's own window is fractional
    which = []
    if case["stats"]:
        which.append("stats")
    if case["toggles"]:
        which.append("artifacts")
    if case["cdr"]:
        which.append("cdr")
    if case["tables"]:
        which += ["companions", "summon_time"]
    out = sensitivity.run(class_module, inputs, which=which)
    diffs = []
    n = [0]
    base_total = wb["summary"]["total"]

    def chk(name, wbv, eng, atol=0.0, frac=False, dimensionless=False):
        """atol = absolute slack (dollars unless ``dimensionless``); ``frac`` = the compared quantity depends on a fractional companion window."""
        n[0] += 1
        frac = frac or frac_case
        if frac and atol and not dimensionless:
            atol = max(atol, FRAC_ATOL * base_total)
        if not close(wbv, eng, max(rtol, FRAC_RTOL) if frac else rtol, atol):
            diffs.append((name, wbv, eng))
    atol_total = 1e-12 * base_total       # a zero gain is a difference of two huge totals: a few ulp of the total is rounding noise
    chk("baseline.total", base_total, out["baseline_total"])
    chk("baseline.boss_only", wb["summary"]["boss_only"], out["baseline_boss_total"])
    chk("baseline.normal_only", wb["summary"]["normal_only"], out["baseline_normal_total"])
    if "stats" in out:
        rows = {r["key"]: r for r in out["stats"]["rows"]}
        for key, blk in wb["stats"].items():
            r = rows[key]
            fr = key in FRAC_STATS
            chk(f"stat.{key}.block_total", blk["total"], r["new_total"], frac=fr)
            chk(f"stat.{key}.block_boss", blk["boss"], r["new_boss_total"], frac=fr)
            chk(f"stat.{key}.block_normal", blk["normal"], r["new_normal_total"], frac=fr)
            chk(f"stat.{key}.current", blk["current"], r["current"])
            chk(f"stat.{key}.new", blk["new"], r["new"])
            chk(f"stat.{key}.dps_gain", blk["dps_gain"], r["dps_gain"], atol_total, frac=fr)
            chk(f"stat.{key}.pct_gain", blk["pct_gain"], r["pct_gain"], 1e-12 * 100, frac=fr, dimensionless=True)
            if fr or frac_case:      # 1 / (a gain error of ~1e-9 x Total): compared loosely
                if not isinstance(blk["units_per_1pct"], str):
                    n[0] += 1
                    if not close(blk["units_per_1pct"], r["units_per_1pct"], 1e-4):
                        diffs.append((f"stat.{key}.units_per_1pct", blk["units_per_1pct"], r["units_per_1pct"]))
                continue
            u = blk["units_per_1pct"]
            if isinstance(u, str):                       # "n/a" (no gain)
                chk(f"stat.{key}.units_per_1pct", None, r["units_per_1pct"])
            elif r["units_per_1pct"] is not None and abs(r["pct_gain"] - 100) < 1e-9:
                pass                                     # 1/(tiny rounding noise): not meaningful
            else:
                chk(f"stat.{key}.units_per_1pct", u, r["units_per_1pct"])
    if "artifacts" in out:
        rows = {r["key"]: r for r in out["artifacts"]["rows"]}
        for art, blk in wb["toggles"].items():
            r = rows[art]
            fr = art in FRAC_TOGGLES       # adds a fractional amount to the summoning window (see FRAC_RTOL)
            chk(f"toggle.{art}.dps_gain", blk["dps_gain"], r["dps_gain"], atol_total, frac=fr)
            chk(f"toggle.{art}.pct_gain", blk["pct_gain"], r["pct_gain"], 1e-12 * 100, frac=fr, dimensionless=True)
            chk(f"toggle.{art}.unlocked", bool(blk["unlocked"]), r["unlocked"])
            if not r["no_dps_effect"]:
                chk(f"toggle.{art}.block_total", blk["total"], r["new_total"], frac=fr)
            if r["no_dps_effect"]:
                chk(f"toggle.{art}.no_dps_effect_gain", case["potential"].get(art, 0.0), r["dps_gain"], atol_total)
        # ranking among the compared toggles: same order as the workbook's pct gain (ties by table position, near-ties ignored)
        order_wb = sorted(wb["toggles"], key=lambda a: -wb["toggles"][a]["pct_gain"])
        pos = {k: i for i, k in enumerate(out["artifacts"]["ranking"])}
        for a_, b_ in zip(order_wb, order_wb[1:]):
            if not (wb["toggles"][a_]["unlocked"] and wb["toggles"][b_]["unlocked"]):
                continue
            pa, pb = wb["toggles"][a_]["pct_gain"], wb["toggles"][b_]["pct_gain"]
            if close(pa, pb, 1e-9):
                continue
            n[0] += 1
            if pos[a_] > pos[b_]:
                diffs.append((f"ranking.{a_}>{b_}", pa, pb))
    if "cdr" in out:
        by_cdr = {r["cdr"]: r for r in out["cdr"]["rows"]}
        for blk in wb["cdr"]:
            r = by_cdr[blk["cdr"]]
            chk(f"cdr.{blk['cdr']}.total", blk["table_total"], r["total_dps"])
            chk(f"cdr.{blk['cdr']}.block_total", blk["total"], r["total_dps"])
            if blk.get("step_prev_kept", True):       # the step is the difference to the previous milestone's block (deleted from a subset copy otherwise)
                chk(f"cdr.{blk['cdr']}.step", blk["table_step"], r["step_gain"], atol_total)
            chk(f"cdr.{blk['cdr']}.pct", blk["table_pct"], r["pct_gain"], 1e-12 * 100, dimensionless=True)
    if "companions" in out:
        rows = {r["name"]: r for r in out["companions"]["rows"]}
        for c in wb["companions"]:
            r = rows[c["name"]]
            chk(f"companion.{c['name']}.level", c["level"], r["level"])
            chk(f"companion.{c['name']}.gain", c["gain"], r["dps_gain"], atol_total, frac=True)
            chk(f"companion.{c['name']}.pct", c["pct"], r["pct_gain"], 1e-12 * 100, frac=True, dimensionless=True)
            chk(f"companion.{c['name']}.unlocked", bool(c["unlocked"]), r["unlocked"])
            if r["unlocked"]:
                chk(f"companion.{c['name']}.rank", c["rank"], r["rank_position"])
    if "summon_time" in out:
        for blk, r in zip(wb["summon_time"], out["summon_time"]["rows"]):
            x = blk["total_pct"]
            chk(f"summon.{x}.total", x, r["total_pct"])
            # (relative changes between two windows, both fractional: the 1e-9-level artifact of each shows up as an absolute 1e-8 on a ratio)
            for k in ("avg_boss_dps_change", "boss_phase_time_factor", "boss_damage_change"):
                chk(f"summon.{x}.{k}", None if isinstance(blk[k], str) else blk[k], r[k], 1e-8, frac=True, dimensionless=True)
            chk(f"summon.{x}.normal_dps_change", blk["normal_dps_change"], r["normal_dps_change"], 1e-8, frac=True, dimensionless=True)
            chk(f"summon.{x}.weighted_dps_change", blk["weighted_dps_change"], r["weighted_dps_change"], 1e-8, frac=True, dimensionless=True)
    return n[0], diffs


def run_golden(class_module, golden_path, rtol=1e-9, verbose=False, only=None):
    golden = json.loads(Path(golden_path).read_text())
    bad, total = {}, 0
    for cid, case in golden["cases"].items():
        if only and cid != only:
            continue
        n, diffs = compare_case(class_module, cid, case, rtol)
        total += n
        if verbose:
            print(f"{'ok  ' if not diffs else 'DIFF'} {cid:22s} {n:4d} values", flush=True)
        if diffs:
            bad[cid] = diffs
    return len(golden["cases"]), total, bad
