#!/usr/bin/env python3
"""Run the ORIGINAL ``src/verify_fp_mage_workbook.py`` against a workbook-free stand-in and print its numbers as JSON.

The verify script is an import-time script: it reads the Inputs / CompanionsInput sheets through ``openpyxl.load_workbook``, imports
the builder for row maps, prints, and finally evaluates the live workbook with the ``formulas`` package.  This runner

  * patches ``openpyxl.load_workbook`` with a fake that serves exactly the cells the script reads (Inputs: the content-type header
    row 2, column B for ``level`` / ``content_type``, the active content type's column for everything else; CompanionsInput:
    name in column A, level in column B),
  * executes the script's own source text unchanged up to (not including) its ``import formulas`` cross-check section (so no
    10 MB workbook is opened and the ``formulas`` package is never imported),
  * collects the resulting module globals.

The reference file is never modified.  Usage::

    run_reference.py CASES.json OUT.json        # CASES.json = [[case_id, inputs], ...]

(one process handles all cases; each case runs in a fresh namespace).
"""
import contextlib
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src"
VERIFY = SRC / "verify_fp_mage_workbook.py"
CUT_MARKER = "\nimport formulas"          # everything from here on is the live-workbook (formulas) cross-check

sys.path.insert(0, str(SRC))
import openpyxl  # noqa: E402  (only the reference side may use it)
import build_fp_mage_workbook as bm  # noqa: E402  (row map / content types the verify script itself imports)
import companion_kits as ck  # noqa: E402

_SOURCE = VERIFY.read_text()
assert CUT_MARKER in _SOURCE
_SOURCE = _SOURCE.split(CUT_MARKER)[0]


class _Cell:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class _Sheet:
    def __init__(self, cells, max_row):
        self._cells = cells
        self.max_row = max_row

    def cell(self, row, column, value=None):
        return _Cell(self._cells.get((row, column)))


class _Workbook:
    def __init__(self, sheets):
        self._sheets = sheets

    def __getitem__(self, name):
        return self._sheets[name]


def fake_workbook(inputs):
    ct = inputs["content_type"]
    col = 3 + bm.CONTENT_TYPES.index(ct)
    cells = {(2, 3 + i): name for i, name in enumerate(bm.CONTENT_TYPES)}
    cells[(bm.IN["level"], 2)] = inputs["level"]
    cells[(bm.IN["content_type"], 2)] = ct
    for key, value in inputs.items():
        if key in ("level", "content_type", "companion_level"):
            continue
        cells[(bm.IN[key], col)] = value
    comp = {}
    for i, name in enumerate(ck.COMPANIONS_ORDER):
        r = bm.COMPANIONS_INPUT_FIRST_ROW + i
        comp[(r, 1)] = name
        comp[(r, 2)] = inputs["companion_level"] if (name == inputs["companion_choice"] and inputs["companion_level"] >= 1) else "Not unlocked"
    return _Workbook({"Inputs": _Sheet(cells, 60), "CompanionsInput": _Sheet(comp, bm.COMPANIONS_INPUT_LAST_ROW)})


def _plain(v):
    """JSON-safe copy of a result value (floats keep their exact repr)."""
    if isinstance(v, bool) or v is None or isinstance(v, (int, float, str)):
        return v
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items() if not callable(x)}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    raise TypeError(type(v))


SCALARS = ("attack", "stat_damage", "actions_per_second", "cast_rate", "basic_attacks_per_second", "avg_buff_mult", "as_bonus",
           "burning_magic_mult", "elemental_decrease_mult", "monster_defense", "fight_duration", "monster_type", "normal_weight",
           "status_on", "skill_coefficient_base", "buff_cast_startup_time", "element_amp_pct", "arcane_aim_pct", "fervent_drain_pct",
           "buff_mastery_pct", "fixed_duration_active", "hasstun", "stf_b", "stf_n", "attack_bucket_sum", "PHI_UNIF", "ignite_unit_dps",
           "companion_dps", "total_dps", "basic_dps")


def run_case(inputs):
    ns = {"__name__": "verify_reference", "__file__": str(VERIFY)}
    real = openpyxl.load_workbook
    openpyxl.load_workbook = lambda *a, **k: fake_workbook(inputs)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(_SOURCE, str(VERIFY), "exec"), ns)
    finally:
        openpyxl.load_workbook = real
    out = {k: _plain(ns[k]) for k in SCALARS if k in ns}
    out["skill_dps"] = _plain(ns["skill_dps"])
    out["branch_pairs"] = {k: [v[0], v[1], v[2], v[3], v[4]] for k, v in ns["_BRANCH_PAIRS"].items()}
    out["engine_n"] = _plain(ns["ENGINE_N"])
    out["phi_rows"] = _plain(ns["PHI_ROWS"])
    out["meteor_x"] = _plain(ns["meteor_x"])
    out["meteor_proc_rate"] = _plain(ns["meteor_proc_rate"])
    out["ignite_ticks_per_s"] = _plain(ns["ignite_ticks_per_s"])
    out["flame_haze_dot_stack_multiplier"] = _plain(ns["flame_haze_dot_stack_multiplier"])
    out["flame_haze_total_stacks"] = _plain(ns["flame_haze_total_stacks"])
    cr = ns["companion_result"]
    out["companion"] = (None if cr is None else {k: _plain(v) for k, v in cr.items() if not callable(v) and isinstance(v, (int, float, str, bool))})
    # boss-only / normal-only sums exactly as the script's own companion block forms them (same order of summation)
    w = ns["normal_weight"]
    pb = pn = 0.0
    for key, val in list(ns["skill_dps"].items()) + [("BASIC_ATTACK", ns["basic_dps"])]:
        pair = ns["_BRANCH_PAIRS"].get(key)
        if pair is None:
            continue
        bd, nd, explicit, bm_, nm_ = pair
        if explicit:
            pb += bd
            pn += nd
        else:
            denom = (1 - w) * bm_ + w * nm_
            pb += val * bm_ / denom
            pn += val * nm_ / denom
    out["player_boss_dps"], out["player_normal_dps"] = pb, pn
    if "pb_total" in ns:     # the script computed them itself (companion on): must be the very same numbers
        assert ns["pb_total"] == pb and ns["pn_total"] == pn, "harness boss/normal sums differ from the script's"
    return out


def main():
    cases = json.loads(Path(sys.argv[1]).read_text())
    results = {}
    for cid, inputs in cases:
        results[cid] = {"inputs": inputs, "out": run_case(inputs)}
    Path(sys.argv[2]).write_text(json.dumps(results))


if __name__ == "__main__":
    main()
