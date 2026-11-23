"""The callables behind the few per-class options of the artifacts golden (``test_artifacts.py``); the DATA options (Calc columns, extra Summary rows) are in
``registry.py``.  ``CONFIG[key]()`` -> extra keyword arguments of ``artifacts_harness.ArtifactsTest``.

* ``fp_mage``: a second golden file, ``fp_mage_artifacts_golden_special.json`` (a list of ``{"name", "inputs", "artifacts": [{"artifact": <workbook name>, "star"}],
  "workbook": {total_dps, boss_dps, normal_dps, companion_dps}}``, written by ``artifact_reference_special.py``), is loaded too when it exists (skipped with a notice
  otherwise); the workbook's artifact NAMES are mapped to the engine ids.  Its Summary values are the base set with the Elemental Decrease multiplier instead of the cast rate.
* ``marksman``: Summary's Global Critical Damage Bonus (row 20) is Sharp Eyes' average alone; the engine's ``crit_damage_bonus`` adds the Crit Damage artifacts.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import artifacts_harness as AH  # noqa: E402

GOLDEN_SPECIAL = HERE / "fp_mage_artifacts_golden_special.json"
# Summary values compared (the base set with the Elemental Decrease multiplier instead of the cast rate)
FP_MAGE_SUMMARY = (("avg_buff_mult", "avgbuff", "avg_buff_mult"), ("elemental_decrease_mult", "ed_mult", "elemental_decrease_mult"),
                   ("actions_per_second", "aps", "actions_per_second"), ("startup", "startup", "buff_cast_startup_time"))


def special_engine_inputs(entry):
    """Engine inputs of a special-file entry: workbook defaults for the content type (non-applicable fields None), overridden by the entry's
    inputs, plus the artifact slots (workbook names -> engine ids)."""
    from engine import artifacts as art
    inputs = entry["inputs"]
    d = _fp_mage().defaults(inputs["content_type"])
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
        res = _fp_mage().compute(special_engine_inputs(e))
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


def _fp_mage():
    from engine.classes import fp_mage
    return fp_mage


def extra_summary(chk, wb, s, d):
    # Summary's Global Critical Damage Bonus (row 20) is Sharp Eyes' average alone; the engine's ``crit_damage_bonus`` adds the Crit Damage artifacts
    chk("summary.crit_damage_bonus", s["20"] + wb["artifacts"]["AGG_CRIT_DAMAGE"], d["crit_damage_bonus"])


CONFIG = {"fp_mage": lambda: dict(special=run_special, summary=FP_MAGE_SUMMARY),
          "marksman": lambda: dict(extra_summary=extra_summary)}
