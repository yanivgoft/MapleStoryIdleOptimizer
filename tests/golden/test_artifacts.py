#!/usr/bin/env python3
"""Golden test: ``engine.classes.<class>.compute`` WITH artifacts equipped against the class's WORKBOOK (evaluated with ``formulas`` by
``<class>_artifact_reference.py``; numbers frozen in tests/golden/<class>_artifacts_golden.json).  ONE parametrised test for all classes of ``registry.py``;
plain ``python3`` runnable, also pytest-collectable (``test_artifacts_match_workbook[<class>]``).

    python3 tests/golden/test_artifacts.py                      # every class, rel 1e-9 on every compared value; exits 1 on any difference
    python3 tests/golden/test_artifacts.py --class hero         # one class (repeatable)
    python3 tests/golden/test_artifacts.py --class hero --rtol 1e-6 -v

The shared body is ``artifacts_harness.py``; the per-class options (Calc columns, extra Summary rows) are data in ``registry.py``, the callables in
``artifacts_extras.py``.
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import artifacts_harness as AH  # noqa: E402
import registry  # noqa: E402


def make_test(cid):
    """The ``ArtifactsTest`` of one class (options from the registry entry)."""
    e = registry.CLASSES[cid]
    opts = dict(e.artifacts)
    extras = opts.pop("extras", None)
    if extras:
        import artifacts_extras
        opts.update(artifacts_extras.CONFIG[extras]())
    return AH.ArtifactsTest(e.engine(), e.artifacts_golden_path, **opts)


def pytest_generate_tests(metafunc):
    if "cid" in metafunc.fixturenames:
        metafunc.parametrize("cid", list(registry.CLASSES))


def test_artifacts_match_workbook(cid):
    make_test(cid).assert_matches()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="classes", action="append", choices=list(registry.CLASSES), help="class id (repeatable); default: all classes")
    ap.add_argument("--rtol", type=float, default=1e-9)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    classes = a.classes or list(registry.CLASSES)
    rc = 0
    for cid in classes:
        if len(classes) > 1:
            print(f"--- {cid}")
        rc |= make_test(cid).main(a.rtol, a.verbose)
    return rc


if __name__ == "__main__":
    sys.exit(main())
