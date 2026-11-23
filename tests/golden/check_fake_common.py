"""Shared body of ``check_<class>_fake.py``: check that the workbook-free stand-in of ``run_reference_<class>.py`` serves the verify script exactly
the cells the REAL workbook holds.

Only the Inputs and CompanionsInput sheets of ``<Class>/<Class>-DPS-Calculator.xlsx`` are streamed (openpyxl read_only, rows <= 60, no ``formulas``,
nothing else of the 6 MB file is parsed into memory).  For every content type:

  1. the real cells are turned into an inputs dict (the same shape ``engine.classes.<class>.compute`` takes),
  2. the verify script is run once against a fake backed DIRECTLY by the real cells (only B3 level / B4 content type overridden to select the
     content type) and once against the stand-in's ``fake_cells(inputs)``,
  3. every cell the script read through the stand-in must be identical to the real cell, and both runs must give the same Total DPS
     (so the stand-in cannot have silently dropped / shifted an input).

    python3 tests/golden/check_<class>_fake.py            # check only
    python3 tests/golden/check_<class>_fake.py --write    # also write tests/golden/<class>_real_inputs.json (the 10 real columns as golden cases)
"""
import contextlib
import io
import json
import sys
from pathlib import Path

import reference_fake as rf

HERE = Path(__file__).resolve().parent


class Check:
    """One class's check: ``ref`` = its ``reference_fake.Reference``, ``class_id`` / ``workbook_dir`` name the golden / workbook files."""

    def __init__(self, ref, class_id, workbook_dir):
        self.ref, self.class_id = ref, class_id
        self.bm, self.ck, self.openpyxl = ref.bm, ref.ck, ref.openpyxl
        self.XLSX = ref.REPO / workbook_dir / f"{workbook_dir}-DPS-Calculator.xlsx"

    def stream_real_cells(self):
        bm = self.bm
        wb = self.openpyxl.load_workbook(self.XLSX, read_only=True, data_only=False)
        try:
            inputs, comp = {}, {}
            for r, row in enumerate(wb["Inputs"].iter_rows(min_row=1, max_row=60, min_col=1, max_col=12, values_only=True), start=1):
                for c, v in enumerate(row, start=1):
                    if v is not None:
                        inputs[(r, c)] = v
            for r, row in enumerate(wb["CompanionsInput"].iter_rows(min_row=1, max_row=bm.COMPANIONS_INPUT_LAST_ROW + 2, min_col=1, max_col=2,
                                                                      values_only=True), start=1):
                for c, v in enumerate(row, start=1):
                    if v is not None:
                        comp[(r, c)] = v
            return inputs, comp
        finally:
            wb.close()

    def inputs_from_real(self, real_in, real_comp, content_type):
        bm = self.bm
        col = 3 + bm.CONTENT_TYPES.index(content_type)
        d = {}
        for key, row in bm.IN.items():
            if key in ("level", "content_type") or row in bm.COMPUTED_INPUT_ROWS:
                continue
            d[key] = real_in.get((row, col))
        d["level"] = real_in[(bm.IN["level"], 2)]
        d["content_type"] = content_type
        lvl = 0
        for i, name in enumerate(self.ck.COMPANIONS_ORDER):
            if name == d["companion_choice"]:
                v = real_comp.get((bm.COMPANIONS_INPUT_FIRST_ROW + i, 2))
                lvl = int(v) if isinstance(v, (int, float)) and v >= 1 else 0
        d["companion_level"] = lvl
        return d

    def run_verify(self, cells_in, cells_comp, log=None):
        """Run the verify script against fake cells; returns (Total DPS, cells read, the script's namespace)."""
        log = set() if log is None else log

        class _Recording(rf._Sheet):
            def __init__(self, cells, max_row, name):
                super().__init__(cells, max_row)
                self.name = name

            def cell(self, row, column, value=None):
                log.add((self.name, row, column))
                return super().cell(row, column, value)
        wb = rf._Workbook({"Inputs": _Recording(cells_in, 60, "Inputs"),
                           "CompanionsInput": _Recording(cells_comp, self.bm.COMPANIONS_INPUT_LAST_ROW, "CompanionsInput")})
        ns = {"__name__": "verify_reference", "__file__": str(self.ref.VERIFY)}
        real = self.openpyxl.load_workbook
        self.openpyxl.load_workbook = lambda *a, **k: wb
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(self.ref._SOURCE, str(self.ref.VERIFY), "exec"), ns)
        finally:
            self.openpyxl.load_workbook = real
        return ns["total_dps"], log, ns

    def main(self, pre_check=None, post_check=None, line_extra=()):
        """``pre_check()`` runs before the workbook is streamed, ``post_check(ns)`` after the content-type loop (``ns`` = the verify script's namespace of
        the first run); both print their own OK line and exit on a problem.  ``line_extra`` = Inputs keys echoed in every content type's line."""
        bm, ck = self.bm, self.ck
        if pre_check is not None:
            pre_check()
        real_in, real_comp = self.stream_real_cells()
        assert [real_in.get((2, 3 + i)) for i in range(len(bm.CONTENT_TYPES))] == bm.CONTENT_TYPES, "Inputs row 2 headers differ"
        assert [real_comp.get((bm.COMPANIONS_INPUT_FIRST_ROW + i, 1)) for i in range(len(ck.COMPANIONS_ORDER))] == list(ck.COMPANIONS_ORDER), \
            "CompanionsInput names differ"
        cases, problems, ns0 = [], [], None
        for ct in bm.CONTENT_TYPES:
            inputs = self.inputs_from_real(real_in, real_comp, ct)
            # (a) the verify script on the real cells (only B3/B4 select the content type; B4 holds a formula-free value in the real file)
            real_cells = dict(real_in)
            real_cells[(bm.IN["level"], 2)] = inputs["level"]
            real_cells[(bm.IN["content_type"], 2)] = ct
            real_total, _, ns = self.run_verify(real_cells, real_comp)
            ns0 = ns0 or ns
            # (b) the stand-in's cells
            fake_in, fake_comp = self.ref.fake_cells(inputs)
            fake_total, log, _ = self.run_verify(fake_in, fake_comp)
            for sheet, r, c in sorted(log):
                real_v = (real_cells if sheet == "Inputs" else real_comp).get((r, c))
                fake_v = (fake_in if sheet == "Inputs" else fake_comp).get((r, c))
                if sheet == "CompanionsInput" and c == 1 and r < bm.COMPANIONS_INPUT_FIRST_ROW:
                    continue        # title / description / header labels above the companion rows: only compared against the chosen companion's name
                if real_v != fake_v and not (sheet == "CompanionsInput" and c == 2 and isinstance(real_v, (int, float)) and fake_v == "Not unlocked"):
                    # (an unchosen companion's level is read only by name lookup for the chosen one; the stand-in blanks the others)
                    problems.append((ct, sheet, r, c, real_v, fake_v))
            same = real_total == fake_total
            extra = "".join(f", {k} {inputs[k]}" for k in line_extra)
            print(f"{ct:20s} real-cells total {real_total!r}  stand-in total {fake_total!r}  {'OK' if same else 'DIFFERENT'}  "
                  f"(companion {inputs['companion_choice']} Lv{inputs['companion_level']}{extra}, {len(log)} cells read)")
            if not same:
                problems.append((ct, "total", real_total, fake_total))
            cases.append((f"REAL/{ct}", inputs))
        if post_check is not None:
            post_check(ns0)
        if problems:
            print("PROBLEMS:", *problems, sep="\n  ")
            sys.exit(1)
        print("OK: the stand-in serves every cell the verify script reads exactly as the real workbook holds it")
        if "--write" in sys.argv:
            (HERE / f"{self.class_id}_real_inputs.json").write_text(json.dumps(cases, indent=0))
            print(f"wrote {len(cases)} real-workbook cases to {self.class_id}_real_inputs.json")
