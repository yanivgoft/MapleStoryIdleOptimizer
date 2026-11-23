#!/usr/bin/env python3
"""Snapshot test of the ENGINE-NATIVE classes (``registry.NATIVE``: no Excel workbook, so no workbook golden): the engine's current output against
``tests/golden/<id>_snapshot.json`` - every numeric leaf of a generic case matrix (compute for 10 content types x stat sets x companion on/off, a level sweep around every
unlock / mastery threshold, every artifact, 2-5 equipped slots, sensitivity runs, cube / equipment / artifact-potential pricing; see ``snapshot_common.py``).

A snapshot PINS THE ENGINE, it is not an independent source (the independent checks of such a class are its displayed-value test against the user's in-game numbers and
``test_engine_native.py``).  Create it with ``update_goldens.py --create --class <id> --reason "..."``, refresh it after an on-purpose model change with
``update_goldens.py --class <id>`` (dry run) then ``--write --reason "..."``; never hand-edit it.

    python3 tests/golden/test_snapshots.py                     # every engine-native class, rel 1e-9 on every numeric leaf; exits 1 on any difference
    python3 tests/golden/test_snapshots.py --class dawn_warrior
    python3 tests/golden/test_snapshots.py --class dawn_warrior -v --rtol 1e-6

Two checks per class: (1) every stored case re-run from its OWN stored inputs gives the stored output; (2) the case matrix the generator builds NOW (it follows the
class's schema and data module) has exactly the stored case ids - a new threshold / field / content type shows up here and asks for a refresh.  Also pytest-collectable
(``test_snapshot_matches_engine[<id>]``, ``test_case_matrix_is_current[<id>]``).
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import registry  # noqa: E402
import snapshot_common as SN  # noqa: E402


def compare_snapshot(cid, rtol=SN.DEFAULT_RTOL, verbose=False, gdir=None, only=None, max_cases=None):
    """-> (n cases, n leaves compared, {case id: [(path, stored, engine), ...]}); raises FileNotFoundError when the class has no snapshot yet."""
    path = SN.snapshot_path(cid, gdir)
    if not path.exists():
        raise FileNotFoundError(f"{path.name}: no snapshot yet - create it with: python3 tests/golden/update_goldens.py --create --class {cid} --reason \"...\"")
    stored = SN.load(path)
    bad, n_leaves, n = {}, 0, 0
    for case_id, case in stored["cases"].items():
        if only and only not in case_id:
            continue
        if max_cases is not None and n >= max_cases:
            break
        n += 1
        n_leaves += SN.count_leaves(case["out"])
        diffs = SN.diff_leaves(case["out"], SN.rerun(cid, case), rtol)
        if verbose:
            print(f"{'ok  ' if not diffs else 'DIFF'} {case_id}")
        if diffs:
            bad[case_id] = diffs
    return n, n_leaves, bad


def matrix_problems(cid, gdir=None):
    """Case ids the generator builds now vs the stored ones: (missing from the snapshot, no longer generated)."""
    stored = set(SN.load(SN.snapshot_path(cid, gdir))["cases"])
    now = set(SN.matrix(cid))
    return sorted(now - stored), sorted(stored - now)


def pytest_generate_tests(metafunc):
    if "cid" in metafunc.fixturenames:
        metafunc.parametrize("cid", list(registry.NATIVE))          # (no engine-native class registered: pytest skips the empty parameter set)


def test_snapshot_matches_engine(cid):
    n, _leaves, bad = compare_snapshot(cid)
    assert n > 0 and not bad, f"{len(bad)} of {n} snapshot cases differ: " + "; ".join(f"{k}: {SN.fmt_path(v[0][0])}" for k, v in list(bad.items())[:5])


def test_case_matrix_is_current(cid):
    added, removed = matrix_problems(cid)
    assert not added and not removed, f"case matrix changed (run update_goldens.py --class {cid}, then --write): +{added[:5]} -{removed[:5]}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="classes", action="append", choices=list(registry.NATIVE), help="engine-native class id (repeatable); default: all of them")
    ap.add_argument("--rtol", type=float, default=SN.DEFAULT_RTOL)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--case", help="only the cases whose id contains this substring")
    ap.add_argument("--golden-dir", help="directory of the snapshot files (default: tests/golden)")
    a = ap.parse_args(argv)
    classes = a.classes or list(registry.NATIVE)
    if not classes:
        print("no engine-native class registered (tests/golden/registry.py NATIVE): nothing to do")
        return 0
    rc = 0
    for cid in classes:
        if len(classes) > 1:
            print(f"--- {cid}")
        try:
            n, leaves, bad = compare_snapshot(cid, a.rtol, a.verbose, a.golden_dir, a.case)
            added, removed = ([], []) if a.case else matrix_problems(cid, a.golden_dir)
        except FileNotFoundError as ex:
            print(f"FAIL: {ex}")
            rc = 1
            continue
        for case_id, diffs in bad.items():
            print(f"MISMATCH {case_id}: {len(diffs)} leaf(s)")
            for path, old, new in diffs[:6]:
                print(f"    {SN.fmt_path(path)}: snapshot {old!r} engine {new!r}")
        if added or removed:
            print(f"CASE MATRIX CHANGED: {len(added)} new case id(s) {added[:4]}, {len(removed)} no longer generated {removed[:4]} -> update_goldens.py --class {cid} (dry run), then --write --reason \"...\"")
        ok = not bad and not added and not removed
        print(f"{'OK' if ok else 'FAIL'}: {n} snapshot cases, {leaves} numeric/string leaves compared, {sum(len(v) for v in bad.values())} differences (rtol {a.rtol:g})")
        rc |= 0 if ok else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
