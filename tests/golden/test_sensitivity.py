#!/usr/bin/env python3
"""Golden test: ``engine.sensitivity`` against the class WORKBOOK's Sensitivity sheet (evaluated with ``formulas`` on Sensitivity-slimmed copies by
``sens_reference_generic.py --class <id>`` / ``sens_reference.py`` for FP-Mage; numbers frozen in tests/golden/<class>_sensitivity_golden.json).  ONE test module for
all classes of ``registry.py``; plain ``python3`` runnable, also pytest-collectable (``test_<name>[<class>]``).

    python3 tests/golden/test_sensitivity.py                          # every class: rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_sensitivity.py --class hero             # one class (repeatable)
    python3 tests/golden/test_sensitivity.py --class hero -v --rtol 1e-6
    python3 tests/golden/test_sensitivity.py --class hero --case "S/WB140/a"

Per class: the golden comparison (the class-agnostic ``sens_compare_generic.py``) plus engine-only tests.  The tests every class repeats (hooks are no-ops, API
shape, equip-toggle direction invariance, the Final Damage +1% sweep) are in ``sens_test_common.py``; what is specific to a class - the spec == builder check
(STAT_SWEEP, STATUS_REBUILD_KEYS, COMPANION_FULL_SEARCH_KEYS, SUMMON_TIME_KEYS, PASSIVE_DELTA_SLOT, the stat maps ...), the baked-in artifact pairs, the pairs
of the toggle test and the data of the shared tests - is in ``sens_extras/<class>.py`` (protocol: ``sens_test_common.plan``).
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import registry  # noqa: E402
import sens_test_common as SC  # noqa: E402
import factor_mode  # noqa: E402

FACTOR_MODE = factor_mode.pin("legacy")        # workbook golden + engine-only checks of the workbook classes: the workbooks clamp skill levels at 300

_PLANS = {}


def _plan(cid):
    if cid not in _PLANS:
        _PLANS[cid] = SC.plan(cid)
    return _PLANS[cid]


def pytest_generate_tests(metafunc):
    """test_<name>[<class>] for the classes that have that test; test_extras[<class>-<function>] for the class-specific functions."""
    name = metafunc.function.__name__
    if name == "test_extras":
        pairs = [(cid, fn) for cid in registry.CLASSES for fn, _f in _plan(cid)[1] + _plan(cid)[2]]
        metafunc.parametrize("cid,fn", pairs, ids=[f"{c}-{f}" for c, f in pairs])
    elif "cid" in metafunc.fixturenames:
        key = name[len("test_"):]
        metafunc.parametrize("cid", [cid for cid in registry.CLASSES if key in _plan(cid)[0]])


def test_static(cid):
    """The spec reproduces the builder's tables (so a builder change that is not mirrored in the spec fails here)."""
    _plan(cid)[0]["static"]()


def test_hooks_are_noops_without_sens(cid):
    """compute() is untouched by the hook plumbing: an explicit empty ``_sens`` is the same as none."""
    _plan(cid)[0]["hooks_are_noops_without_sens"]()


def test_api_shape(cid):
    """`which` selection, JSON-serialisable output, the no-effect flag, the potential-gain term, the live Shamaness row and the naive switch."""
    _plan(cid)[0]["api_shape"]()


def test_final_damage_sweep_is_exactly_one_percent(cid):
    """The +1% multiplicative Final Damage step bumps the FULL bucket: the ratio is exactly 1.01 wherever nothing else moves."""
    _plan(cid)[0]["final_damage_sweep_is_exactly_one_percent"]()


def test_toggle_direction_invariance(cid):
    """CLAUDE.md item 15 / checklist 8c, engine-only: an equip toggle reports the identical gain and % gain from both directions."""
    _plan(cid)[0]["toggle_direction_invariance"]()


def test_golden(cid):
    _plan(cid)[0]["golden"]()


def test_extras(cid, fn):
    """The class's own tests (``EXTRA`` / ``GOLDEN_EXTRA`` of its ``sens_extras`` module)."""
    dict(_plan(cid)[1] + _plan(cid)[2])[fn]()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="classes", action="append", choices=list(registry.CLASSES), help="class id (repeatable); default: all classes")
    ap.add_argument("--rtol", type=float, default=1e-9)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--case", help="only the golden case with this id")
    a = ap.parse_args(argv)
    classes = a.classes or list(registry.CLASSES)
    rc = 0
    for cid in classes:
        if len(classes) > 1:
            print(f"--- {cid}")
        rc |= SC.run_cli(cid, a.rtol, a.verbose, a.case)
    return rc


if __name__ == "__main__":
    sys.exit(main())
