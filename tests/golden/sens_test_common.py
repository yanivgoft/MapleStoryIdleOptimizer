"""Shared pieces of ``test_<class>_sensitivity.py`` (engine.sensitivity vs the class workbook's Sensitivity sheet, ``<class>_sensitivity_golden.json``): the
builder loader, the inputs of the engine-only tests, the hook / golden tests and the command line.  The comparison logic itself is ``sens_compare_generic.py``;
what is specific to a class (the spec == builder tables, the baked-in artifact checks, the API shape) stays in its own test file."""
import argparse
import importlib
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import sens_compare_generic as C  # noqa: E402


class SensTest:
    def __init__(self, class_id, class_module, golden, class_name):
        self.class_id, self.module, self.GOLDEN, self.class_name = class_id, class_module, golden, class_name

    def builder(self):
        """The class's builder module (module-level tables only; needs openpyxl, None without it)."""
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            return None
        sys.path.insert(0, str(REPO / "src"))
        spec = importlib.util.spec_from_file_location(f"{self.class_id}_bmod_sens", REPO / "src" / f"build_{self.class_id}_workbook.py")
        bm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bm)
        return bm

    def inputs(self, content, artifacts, **over):
        """Engine inputs of a stat-set-S character at Lv140 with Blaze Wizard and the given equipped artifacts (all 36 at their sens-case stars)."""
        from sens_cases import STARS
        make_inputs = importlib.import_module(f"{self.class_id}_cases").make_inputs
        STATS_S = importlib.import_module(f"{self.class_id}_sens_cases").STATS_S
        d = make_inputs(content, 140, STATS_S, "blaze", **over)
        d["artifacts"] = artifacts
        d["artifact_stars"] = dict(STARS)
        return d

    def test_hooks_are_noops_without_sens(self):
        """compute() is untouched by the hook plumbing: an explicit empty ``_sens`` is the same as none."""
        inp = self.inputs("World Boss", [{"key": "bottle_of_emotion", "star": 5}])
        a = self.module.compute(inp)["total_dps"]
        b = self.module.compute(dict(inp, _sens={}))["total_dps"]
        assert a == b

    def test_golden(self):
        if not self.GOLDEN.exists():
            return
        n_cases, n_values, bad = C.run_golden(self.module, self.GOLDEN)
        assert not bad, {k: v[:5] for k, v in bad.items()}

    def main(self, pre_tests, golden_tests, ok_message):
        """The command line: ``--rtol`` (default 1e-9), ``-v``, ``--case ID``.  ``pre_tests`` run first, ``golden_tests`` only when the golden file exists."""
        ap = argparse.ArgumentParser()
        ap.add_argument("--rtol", type=float, default=1e-9)
        ap.add_argument("-v", "--verbose", action="store_true")
        ap.add_argument("--case")
        a = ap.parse_args()
        for t in pre_tests:
            t()
        if self.GOLDEN.exists():
            for t in golden_tests:
                t()
        print(ok_message)
        if not self.GOLDEN.exists():
            print("no golden file yet")
            sys.exit(1)
        n_cases, n_values, bad = C.run_golden(self.module, self.GOLDEN, a.rtol, a.verbose, a.case)
        for cid, diffs in bad.items():
            for name, wbv, eng in diffs[:25]:
                rel = abs(wbv - eng) / max(abs(wbv), abs(eng), 1e-300) if isinstance(wbv, (int, float)) and isinstance(eng, (int, float)) else float("nan")
                print(f"  {cid}: {name}: workbook {wbv!r} engine {eng!r} rel {rel:.2e}")
        print(f"{'OK' if not bad else 'FAIL'}: {n_cases} cases, {n_values} values compared, {sum(len(v) for v in bad.values())} differences (rtol {a.rtol})")
        sys.exit(1 if bad else 0)
