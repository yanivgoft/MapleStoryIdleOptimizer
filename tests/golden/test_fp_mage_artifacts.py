#!/usr/bin/env python3
"""Golden test: ``engine.classes.fp_mage.compute`` WITH artifacts equipped against the FP-Mage WORKBOOK (evaluated with ``formulas`` by
``artifact_reference.py``; numbers frozen in tests/golden/fp_mage_artifacts_golden.json).  Plain ``python3`` runnable, also pytest-collectable.

    python3 tests/golden/test_fp_mage_artifacts.py             # rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_fp_mage_artifacts.py --rtol 1e-6 -v

A second file, ``fp_mage_artifacts_golden_special.json`` (a list of ``{"name", "inputs", "artifacts": [{"artifact": <workbook name>, "star"}],
"workbook": {total_dps, boss_dps, normal_dps, companion_dps}}``, written by ``artifact_reference_special.py``), is loaded too when it exists (skipped with
a notice otherwise); the workbook's artifact NAMES are mapped to the engine ids.

The shared body is ``artifacts_harness.py``.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from engine.classes import fp_mage  # noqa: E402
import artifacts_harness as AH  # noqa: E402

GOLDEN = HERE / "fp_mage_artifacts_golden.json"
GOLDEN_SPECIAL = HERE / "fp_mage_artifacts_golden_special.json"
# Summary values compared (the base set with the Elemental Decrease multiplier instead of the cast rate)
SUMMARY = (("avg_buff_mult", "avgbuff", "avg_buff_mult"), ("elemental_decrease_mult", "ed_mult", "elemental_decrease_mult"),
           ("actions_per_second", "aps", "actions_per_second"), ("startup", "startup", "buff_cast_startup_time"))


def special_engine_inputs(entry):
    """Engine inputs of a special-file entry: workbook defaults for the content type (non-applicable fields None), overridden by the entry's
    inputs, plus the artifact slots (workbook names -> engine ids)."""
    from engine import artifacts as art
    inputs = entry["inputs"]
    d = fp_mage.defaults(inputs["content_type"])
    d.update(inputs)
    slots = []
    for a in entry.get("artifacts", []):
        name = a.get("artifact", a.get("key"))
        if name in (None, "", art.NONE_LABEL):
            continue
        slots.append({"key": art.LABEL_TO_KEY.get(name, name), "star": a.get("star")})
    d["artifacts"] = slots
    return d


def run_special(rtol=1e-9, verbose=False):
    """(n cases, {name: [(field, workbook, engine)]}) of the special golden file; (0, {}) when it does not exist yet."""
    if not GOLDEN_SPECIAL.exists():
        print(f"notice: {GOLDEN_SPECIAL.name} not found - special artifact cases skipped (re-run once it exists)")
        return 0, {}
    entries = json.loads(GOLDEN_SPECIAL.read_text())
    bad = {}
    for e in entries:
        res = fp_mage.compute(special_engine_inputs(e))
        wb = e["workbook"]
        diffs = []
        for name, wbv, eng in (("total_dps", wb.get("total_dps"), res["total_dps"]), ("boss_dps", wb.get("boss_dps"), res["boss_dps"]),
                               ("normal_dps", wb.get("normal_dps"), res["normal_dps"]),
                               ("companion_dps", wb.get("companion_dps"), res["companion"]["dps"] if res["companion"] else 0.0)):
            if wbv is not None and not AH.close(wbv, eng, rtol):
                diffs.append((name, wbv, eng))
        if verbose:
            t = wb.get("total_dps")
            print(f"{'ok  ' if not diffs else 'DIFF'} special/{e['name']:46s} workbook {t:.12e} engine {res['total_dps']:.12e} rel {abs(t - res['total_dps']) / t:.1e}")
        if diffs:
            bad[e["name"]] = diffs
    return len(entries), bad


TEST = AH.ArtifactsTest(fp_mage, GOLDEN, boss_col="S", normal_col="U", special=run_special, summary=SUMMARY)
compare, run = TEST.compare, TEST.run


def test_fp_mage_artifacts_match_workbook():
    TEST.assert_matches()


if __name__ == "__main__":
    TEST.main()
