"""Shared body of ``test_<class>.py`` (engine vs the frozen numbers of the ORIGINAL verify script, ``<class>_golden.json``).

A class test keeps only what is class-specific (its basic-attack row, its derived scalars, ...) in its own ``compare``; the opening checks, the Status
Effect / KO timeline + companion checks, the run loop and the command line are here.  ``python3 tests/golden/test_<class>.py [--rtol 1e-12]`` exits 1 on
any difference (exact ``==`` by default), the ``test_`` functions are pytest-collectable.
"""
import json
import math
import sys

import factor_mode

FACTOR_MODE = factor_mode.pin("legacy")        # compared with the verify scripts' numbers: the workbooks clamp skill levels at 300 (engine/common/factors.py)


def eq(a, b, rtol):
    if isinstance(a, float) or isinstance(b, float):
        if a == b:
            return True
        return rtol > 0 and math.isclose(a, b, rel_tol=rtol, abs_tol=0.0)
    return a == b


def begin(gold, res, rtol, reference_error=True):
    """(out, diffs, chk, done) of one case: the opening totals are already checked.  ``done`` = the verify script itself crashed on this case (no
    reference numbers): the engine must then not crash and must return a finite, non-negative total (it reads a missing stun vector as zero)."""
    out = gold["out"]
    diffs = []
    if reference_error and "reference_error" in out:
        # The verify script itself crashes (KeyError 'stun_vector': no companion + every player stun locked in a KO content).
        if not (math.isfinite(res["total_dps"]) and res["total_dps"] >= 0):
            diffs.append(("total_dps finite", out["reference_error"], res["total_dps"]))
        return out, diffs, None, True

    def chk(name, g, e):
        if not eq(g, e, rtol):
            diffs.append((name, g, e))

    chk("total_dps", out["total_dps"], res["total_dps"])
    chk("companion_dps", out["companion_dps"], res["companion"]["dps"] if res["companion"] else 0.0)
    chk("player_boss_dps", out["player_boss_dps"], res["player_boss_dps"])
    chk("player_normal_dps", out["player_normal_dps"], res["player_normal_dps"])
    return out, diffs, chk, False


def check_stunned_shares(chk, out, d):
    chk("derived.stunned_share_boss", out["stf_b"], d["stunned_share_boss"])
    chk("derived.stunned_share_normal", out["stf_n"], d["stunned_share_normal"])


def check_engine_and_companion(chk, out, res, casts_keys=False, companion_present=False):
    """The Status Effect / KO timeline engine (phi, casts) and the companion run.  ``casts_keys``: also the engine's cast keys; ``companion_present``: the
    engine must not report a companion the script did not run."""
    chk("engine_on", out["status_on"], res["engine_on"])
    if res["engine_on"]:
        chk("engine.phi_unif", out["PHI_UNIF"], res["engine"]["phi_unif"])
        for k, v in out["engine_n"].items():
            chk(f"engine.casts[{k}]", v, res["engine"]["casts"][k])
        if casts_keys:
            chk("engine.casts keys", sorted(out["engine_n"]), sorted(res["engine"]["casts"]))
        for k, v in out["phi_rows"].items():
            chk(f"engine.phi[{k}]", v, res["engine"]["phi_rows"][k])
    else:
        chk("engine.casts empty", {}, out["engine_n"])
    if out["companion"] is None:
        chk("companion none", None, res["companion"])
    elif companion_present and res["companion"] is None:
        chk("companion present", "present", None)
    else:
        c = res["companion"]
        for k, v in out["companion"].items():
            chk(f"companion.{k}", v, c["details"][k])
        chk("companion.boss", out["companion"]["comp_boss_dps"], c["boss_dps"])
        chk("companion.normal", out["companion"]["comp_norm_dps"], c["normal_dps"])


def run_golden(class_module, golden_path, compare, rtol=0.0, verbose=True):
    golden = json.loads(golden_path.read_text())
    bad = {}
    for cid, case in golden.items():
        res = class_module.compute(case["inputs"])
        diffs = compare(case, res, rtol)
        if diffs:
            bad[cid] = diffs
    if verbose:
        for cid, diffs in bad.items():
            print(f"MISMATCH {cid}: {len(diffs)} field(s)")
            for name, g, e in diffs[:5]:
                print(f"    {name}: golden {g!r} engine {e!r}")
    return len(golden), bad


def main(run, hook_check=None):
    """Command line of a class test.  ``hook_check()`` -> a list of problems of a class-specific check that runs after the golden (printed as ARTIFACT HOOK)."""
    rtol = float(sys.argv[sys.argv.index("--rtol") + 1]) if "--rtol" in sys.argv else 0.0
    n, bad = run(rtol)
    hook = hook_check() if hook_check is not None else []
    for p_ in hook:
        print("ARTIFACT HOOK:", p_)
    if bad or hook:
        print(f"FAILED: {len(bad)} of {n} cases differ (rtol={rtol})" + (f"; artifact-hook problems: {len(hook)}" if hook_check is not None else ""))
        sys.exit(1)
    print(f"OK: {n} golden cases match the verify script " + ("bit-exactly" if rtol == 0 else f"within rtol {rtol}"))
