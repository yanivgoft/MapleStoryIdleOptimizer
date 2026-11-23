"""The workbook-free stand-in shared by every ``run_reference_<class>.py`` (and the ``check_<class>_fake.py`` scripts).

Same technique as ``run_reference.py`` (FP-Mage): ``openpyxl.load_workbook`` is patched with a fake serving exactly the cells the verify script
reads (Inputs: content-type header row 2, column B for ``level`` / ``content_type``, the active content type's column for everything else;
CompanionsInput: name in column A, level in column B), and the script's own source text is executed unchanged.  ``Reference(verify_name,
builder_module)`` binds one class: its verify script, its builder (row map / content types / CompanionsInput rows, which the verify script
imports itself) and the optional replacement of a mid-script ``import formulas`` (the live-workbook helpers are defined before the timeline-engine
block, so that single line becomes ``formulas = None``; the run always stops at the "Cross-check against the actual live workbook" banner).
"""
import contextlib
import importlib
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src"
IMPORT_LINE = "import formulas  # noqa: E402"
CUT_MARKER = "\n# ---------------------------------------------------------------------------\n# Cross-check against the actual live workbook"

sys.path.insert(0, str(SRC))
import openpyxl  # noqa: E402  (only the reference side may use it)
import companion_kits as ck  # noqa: E402


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


def _plain(v):
    """JSON-safe copy of a result value (floats keep their exact repr)."""
    if isinstance(v, bool) or v is None or isinstance(v, (int, float, str)):
        return v
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items() if not callable(x)}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    raise TypeError(type(v))


class Reference:
    def __init__(self, verify_name, builder_name, import_formulas_mid_script=True):
        self.VERIFY = SRC / verify_name
        self.bm = importlib.import_module(builder_name)        # row map / content types the verify script itself imports
        self.ck = ck
        self.openpyxl = openpyxl
        self.REPO = REPO
        self.SRC = SRC
        source = self.VERIFY.read_text()
        if import_formulas_mid_script:
            assert source.count(IMPORT_LINE) == 1 and CUT_MARKER in source
            source = source.replace(IMPORT_LINE, "formulas = None  # (stand-in: the live-workbook cross-check is not run here)").split(CUT_MARKER)[0]
        else:      # the script's only ``import formulas`` sits inside the live-workbook cross-check at the very end: the run simply stops at the banner
            assert source.count("import formulas") == 1 and CUT_MARKER in source and source.index(CUT_MARKER) < source.index("import formulas")
            source = source.split(CUT_MARKER)[0]
            assert "import formulas" not in source
        self._SOURCE = source

    def fake_cells(self, inputs):
        """{(row, col): value} of the Inputs sheet and of CompanionsInput the verify script would read for ``inputs``."""
        bm = self.bm
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
        return cells, comp

    def fake_workbook(self, inputs):
        cells, comp = self.fake_cells(inputs)
        return _Workbook({"Inputs": _Sheet(cells, 60), "CompanionsInput": _Sheet(comp, self.bm.COMPANIONS_INPUT_LAST_ROW)})

    def execute(self, inputs):
        """Run the verify script's own source text against the stand-in for ``inputs``; returns its module namespace."""
        ns = {"__name__": "verify_reference", "__file__": str(self.VERIFY)}
        real = openpyxl.load_workbook
        openpyxl.load_workbook = lambda *a, **k: self.fake_workbook(inputs)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(self._SOURCE, str(self.VERIFY), "exec"), ns)
        finally:
            openpyxl.load_workbook = real
        return ns

    def run_case(self, inputs, scalars, basic=None, hit_rate=None, post_scalars=None):
        """One case's numbers: the verify script's scalars, ``skill_dps``, its branch pairs, the timeline engine and the companion, plus the player's
        boss-only / normal-only sums exactly as the script's own companion block forms them (same order of summation).  ``basic`` = (row key, the
        namespace variable of its DPS) for the classes whose rows may be multiplier-style (the 5-field branch pair; boss DPS = DPS x b / ((1-w) b + w n));
        ``hit_rate`` = "before" / "after" the branch pairs: also keep the script's ``hit_rate``; ``post_scalars(ns, out)`` adds class scalars."""
        ns = self.execute(inputs)
        out = {k: _plain(ns[k]) for k in scalars if k in ns}
        if post_scalars is not None:
            post_scalars(ns, out)
        out["skill_dps"] = _plain(ns["skill_dps"])
        if hit_rate == "before":
            out["hit_rate"] = _plain(ns["hit_rate"])
        if basic is not None:
            out["branch_pairs"] = {k: [v[0], v[1], v[2], v[3], v[4]] for k, v in ns["_BRANCH_PAIRS"].items()}
        else:
            out["branch_pairs"] = {k: [v[0], v[1]] for k, v in ns["_BRANCH_PAIRS"].items()}
        if hit_rate == "after":
            out["hit_rate"] = _plain(ns["hit_rate"])
        out["engine_n"] = _plain(ns["ENGINE_N"])
        out["phi_rows"] = _plain(ns["PHI_ROWS"])
        cr = ns["companion_result"]
        out["companion"] = (None if cr is None else {k: _plain(v) for k, v in cr.items() if not callable(v) and isinstance(v, (int, float, str, bool))})
        # boss-only / normal-only sums exactly as the script's own companion block forms them (same loop, same order of summation)
        if basic is None:
            pb = sum(v[0] for v in ns["_BRANCH_PAIRS"].values())
            pn = sum(v[1] for v in ns["_BRANCH_PAIRS"].values())
        else:
            pb = pn = 0.0
            for key, val in list(ns["skill_dps"].items()) + [(basic[0], ns[basic[1]])]:
                pair = ns["_BRANCH_PAIRS"].get(key)
                if pair is None:
                    continue
                bd, nd, explicit, bm_, nm_ = pair
                if explicit:
                    pb += bd
                    pn += nd
                else:
                    denom = (1 - ns["normal_weight"]) * bm_ + ns["normal_weight"] * nm_
                    pb += val * bm_ / denom
                    pn += val * nm_ / denom
        out["player_boss_dps"], out["player_normal_dps"] = pb, pn
        if "pb_total" in ns:     # the script computed them itself (companion / player-stun block on): must be the very same numbers
            assert ns["pb_total"] == pb and ns["pn_total"] == pn, "harness boss/normal sums differ from the script's"
        return out

    def main(self, run_case):
        """CLI: ``run_reference_<class>.py CASES.json OUT.json`` (CASES.json = [[case_id, inputs], ...])."""
        cases = json.loads(Path(sys.argv[1]).read_text())
        results = {}
        for cid, inputs in cases:
            try:
                out = run_case(inputs)
            except KeyError as e:      # a latent crash of the verify script itself (KO content, no companion, every player stun locked)
                out = {"reference_error": f"KeyError: {e}"}
            results[cid] = {"inputs": inputs, "out": out}
        Path(sys.argv[2]).write_text(json.dumps(results))
