"""Shared body of ``<class>_artifact_reference.py``: ground truth for the artifact golden set - evaluates the class's WORKBOOK (with artifacts equipped) with
the ``formulas`` package.

There is no plain-Python reference for artifacts (the verify scripts ignore them), so every case of ``<class>_artifact_cases.py`` is run through
``<Class>/<Class>-DPS-Calculator.xlsx`` itself.  Per case: a STRIPPED scratch copy is built (like ``data/porting/helpers/sv.py``: Sensitivity sheet
dropped and every formula that reads it replaced by 0; additionally the Companion sheet's comparison / Summoning-Time grid columns C.. are
blanked - the 16 per-companion copies of the companion chain that only feed the Sensitivity / CompanionsInput comparison tables), the Inputs /
artifact slots / ArtifactsInput star levels / companion are set, ONE ``formulas`` evaluation reads Summary / Artifacts / Calc / Companion
cells, the scratch .xlsx is deleted.  Each evaluation takes minutes and several GB: run them ONE AT A TIME (the driver does).

    python3 tests/golden/<class>_artifact_reference.py --list
    python3 tests/golden/<class>_artifact_reference.py --case "G1/World Boss/blaze"            # one evaluation -> $ARTIFACT_REF_SCRATCH/results/<id>.json
    python3 tests/golden/<class>_artifact_reference.py --run-all                                # every missing case, sequential subprocesses
    python3 tests/golden/<class>_artifact_reference.py --assemble                               # results -> tests/golden/<class>_artifacts_golden.json
"""
import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))


def slug(case_id):
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", case_id)


def scalar(v):
    import numpy as np
    try:
        a = np.asarray(v.value).reshape(-1)[0]
    except Exception:
        return str(v)
    if isinstance(a, (bool, np.bool_)):
        return bool(a)
    try:
        return float(a)
    except (TypeError, ValueError):
        return str(a)


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True).stdout.strip()


def rows_standard(bm):
    """(the Summary rows stored with every case, boss-only total row, normal-only total row) of a builder with ``R_*`` constants."""
    return (dict(total=bm.R_TOTAL, boss_only=bm.R_BOSS_ONLY_TOTAL, normal_only=bm.R_NORMAL_ONLY_TOTAL, avgbuff=bm.R_AVGBUFF,
                 aps=bm.R_APS, startup=bm.R_STARTUP_TIME, castrate=bm.R_CASTRATE), bm.R_BOSS_ONLY_TOTAL, bm.R_NORMAL_ONLY_TOTAL)


def rows_summary_row(bm):
    """The same for a builder with a ``SUMMARY_ROW`` dict (Bishop, Ice/Lightning Mage)."""
    SR = bm.SUMMARY_ROW
    return (dict(total=bm.R_TOTAL, boss_only=SR["BOSS_ONLY_TOTAL"], normal_only=SR["NORMAL_ONLY_TOTAL"], avgbuff=SR["AVG_BUFF_MULT"],
                 aps=SR["APS"], startup=SR["STARTUP_TIME"], castrate=SR["CAST_RATE"]), SR["BOSS_ONLY_TOTAL"], SR["NORMAL_ONLY_TOTAL"])


def rows_ed_mult(bm):
    """The same for FP-Mage (Elemental Decrease multiplier instead of the cast rate)."""
    return (dict(total=bm.R_TOTAL, boss_only=bm.R_BOSS_ONLY_TOTAL, normal_only=bm.R_NORMAL_ONLY_TOTAL, avgbuff=bm.R_AVGBUFF,
                 ed_mult=bm.R_ED_MULT, aps=bm.R_APS, startup=bm.R_STARTUP_TIME), bm.R_BOSS_ONLY_TOTAL, bm.R_NORMAL_ONLY_TOTAL)


class ArtifactReference:
    """One class: ``class_id`` / ``workbook_dir`` (``Hero`` -> ``Hero/Hero-DPS-Calculator.xlsx``), its ``cases_module`` (``<class>_artifact_cases``), the
    default scratch dir, the Summary rows read (``summary_rows`` = highest row), the Calc columns read and ``summary_row_map(bm)`` ->
    (the ``rows`` dict stored with every case, the Summary rows of the boss-only / normal-only totals)."""

    def __init__(self, class_id, workbook_dir, cases_module, scratch, summary_rows, calc_cols, summary_row_map, script, golden=None):
        self.class_id, self.cases_module, self.script = class_id, cases_module, script
        self.SCRATCH = Path(os.environ.get("ARTIFACT_REF_SCRATCH", scratch))
        self.RESULTS = self.SCRATCH / "results"
        self.WORKBOOK = REPO / workbook_dir / f"{workbook_dir}-DPS-Calculator.xlsx"
        self.BUILDER_REL = f"src/build_{class_id}_workbook.py"
        self.BUILDER = REPO / self.BUILDER_REL
        self.GOLDEN = HERE / (golden or f"{class_id}_artifacts_golden.json")
        self.workbook_dir, self.summary_rows, self.calc_cols, self.summary_row_map = workbook_dir, summary_rows, calc_cols, summary_row_map

    def cases(self):
        return importlib.import_module(self.cases_module)

    def load_builder(self):
        """The builder module (only its module-level tables are used: input row numbers, sheet cell maps; main() is NOT run)."""
        spec = importlib.util.spec_from_file_location(f"{self.class_id}_bmod", self.BUILDER)
        bm = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(REPO / "src"))
        spec.loader.exec_module(bm)
        return bm

    def build_scratch(self, bm, inputs, out_path):
        import openpyxl
        wb = openpyxl.load_workbook(self.WORKBOOK)
        wi = wb["Inputs"]
        ct = inputs["content_type"]
        col = next(c for c in range(3, 3 + len(bm.CONTENT_TYPES)) if wi.cell(2, c).value == ct)
        wi.cell(bm.IN["level"], 2).value = inputs["level"]
        wi.cell(bm.IN["content_type"], 2).value = ct
        for key, v in inputs.items():
            if key in ("level", "content_type", "artifacts", "companion_level"):
                continue
            if key not in bm.IN:
                raise KeyError(f"input {key!r} is not a workbook Inputs key")
            wi.cell(bm.IN[key], col).value = v
        # equipped slots (every content type's column, like sv.py) + star levels
        labels = [bm.ARTIFACT_LABELS[a["key"]] for a in inputs.get("artifacts", [])]
        labels += ["(none)"] * (len(bm.INPUT_ARTIFACT_SLOT_ROWS) - len(labels))
        for row, label in zip(bm.INPUT_ARTIFACT_SLOT_ROWS, labels):
            for c in range(3, 3 + len(bm.CONTENT_TYPES)):
                wi.cell(row, c).value = label
        wa = wb["ArtifactsInput"]
        for a in inputs.get("artifacts", []):
            wa.cell(bm.ARTIFACTS_INPUT_ROW[a["key"]], 2).value = "Not Unlocked" if a.get("star") is None else int(a["star"])
        # companion level
        choice, clevel = inputs["companion_choice"], inputs["companion_level"]
        wc = wb["CompanionsInput"]
        for name, row in bm.COMPANION_INPUT_ROW.items():
            if name == choice:
                wc.cell(row, 2).value = int(clevel) if clevel else "Not unlocked"
        # strip: Sensitivity (and everything reading it) + the Companion sheet's per-companion comparison / summoning-time grid columns
        for ws_ in wb.worksheets:
            for row_ in ws_.iter_rows():
                for c_ in row_:
                    if isinstance(c_.value, str) and c_.value.startswith("=") and "Sensitivity!" in c_.value:
                        c_.value = 0
        del wb["Sensitivity"]
        wcomp = wb["Companion"]
        for row_ in wcomp.iter_rows(min_col=3):
            for c_ in row_:
                c_.value = None
        wb.save(out_path)

    def evaluate(self, bm, path):
        import formulas
        t0 = time.time()
        model = formulas.ExcelModel().loads(str(path)).finish()
        t1 = time.time()
        sol = model.calculate()
        t2 = time.time()
        cells = {}
        pat = re.compile(r"\]([^']+)'!([A-Z]+[0-9]+)$")
        for k, v in sol.items():
            m = pat.search(k)
            if m:
                cells[(m.group(1).upper(), m.group(2))] = v

        def get(sheet, addr):
            v = cells.get((sheet.upper(), addr))
            return None if v is None else scalar(v)
        out = dict(summary={}, artifacts={}, calc={}, companion={}, timeline_on=None)
        for r in range(1, self.summary_rows + 1):
            v = get("Summary", f"B{r}")
            if v is not None:
                out["summary"][str(r)] = v
        for key, r in bm.ART_ROW.items():
            out["artifacts"][key] = get("Artifacts", f"B{r}")
        for key, r in bm.ROW.items():
            out["calc"][key] = {c: get("Calc", f"{c}{r}") for c in self.calc_cols}
        for name, r in bm.COMPANION_ROW_OF.items():
            out["companion"][name] = get("Companion", f"B{r}")
        out["timeline_on"] = get(*bm.STATUS_MAIN_LAYOUT.s("on").replace("$", "").replace("'", "").split("!"))
        out["rows"], boss_row, normal_row = self.summary_row_map(bm)
        out["total_dps"] = get("Summary", f"B{bm.R_TOTAL}")
        out["boss_only_total"] = get("Summary", f"B{boss_row}")
        out["normal_only_total"] = get("Summary", f"B{normal_row}")
        out["load_s"], out["calc_s"] = round(t1 - t0, 1), round(t2 - t1, 1)
        return out

    def run_case(self, case_id, out_json):
        inputs = dict(self.cases().artifact_cases())[case_id]
        bm = self.load_builder()
        self.SCRATCH.mkdir(exist_ok=True)
        scratch = self.SCRATCH / f"run_{os.getpid()}.xlsx"
        t0 = time.time()
        try:
            self.build_scratch(bm, inputs, scratch)
            t_build = time.time() - t0
            res = self.evaluate(bm, scratch)
        finally:
            if scratch.exists():
                scratch.unlink()
        res.update(case=case_id, build_s=round(t_build, 1), eval_total_s=round(time.time() - t0, 1),
                   max_rss_gb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 2))
        self.RESULTS.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(res))
        print(f"{case_id}: total={res['total_dps']!r} build {res['build_s']}s load {res['load_s']}s calc {res['calc_s']}s rss {res['max_rss_gb']} GB")

    def run_all(self):
        self.RESULTS.mkdir(parents=True, exist_ok=True)
        for cid, _ in self.cases().artifact_cases():
            out = self.RESULTS / f"{slug(cid)}.json"
            if out.exists():
                continue
            r = subprocess.run([sys.executable, str(Path(self.script).resolve()), "--case", cid, "--out", str(out)], timeout=3600)
            if r.returncode != 0:
                print(f"FAILED {cid} (rc={r.returncode})", flush=True)
                break
            for f in self.SCRATCH.glob("run_*.xlsx"):          # never leave a scratch workbook behind
                f.unlink()

    def assemble(self):
        cases_mod = self.cases()
        cases = {}
        for cid, inputs in cases_mod.artifact_cases():
            f = self.RESULTS / f"{slug(cid)}.json"
            if not f.exists():
                print("missing", cid)
                continue
            r = json.loads(f.read_text())
            cases[cid] = dict(inputs=inputs, workbook=r)
        wb_rel = f"{self.workbook_dir}/{self.workbook_dir}-DPS-Calculator.xlsx"
        meta = dict(
            workbook=wb_rel, workbook_sha256=hashlib.sha256(self.WORKBOOK.read_bytes()).hexdigest(),
            workbook_size=self.WORKBOOK.stat().st_size, repo_head=git("rev-parse", "HEAD"),
            workbook_git_status=git("status", "--porcelain", "--", wb_rel, self.BUILDER_REL) or "clean (identical to HEAD)",
            builder_blob=git("rev-parse", f"HEAD:{self.BUILDER_REL}"), workbook_blob=git("rev-parse", f"HEAD:{wb_rel}"),
            strip="Sensitivity sheet dropped (formulas reading it = 0); Companion sheet columns C.. blanked; Inputs/slots/stars/companion set via openpyxl",
            evaluator="formulas " + __import__("formulas").__version__,
        )
        self.GOLDEN.write_text(json.dumps(dict(meta=meta, toggle_pairs=[list(t) for t in cases_mod.TOGGLE_PAIRS],
                                               equiv_pairs=[list(t) for t in cases_mod.EQUIV_PAIRS], cases=cases), indent=0))
        secs = [c["workbook"]["eval_total_s"] for c in cases.values()]
        print(f"wrote {self.GOLDEN}: {len(cases)} cases; evaluation seconds min/mean/max = {min(secs):.0f}/{sum(secs)/len(secs):.0f}/{max(secs):.0f}")

    def main(self):
        ap = argparse.ArgumentParser()
        ap.add_argument("--list", action="store_true")
        ap.add_argument("--case")
        ap.add_argument("--out")
        ap.add_argument("--run-all", action="store_true")
        ap.add_argument("--assemble", action="store_true")
        a = ap.parse_args()
        if a.list:
            for cid, _ in self.cases().artifact_cases():
                print(cid, "done" if (self.RESULTS / f"{slug(cid)}.json").exists() else "")
        elif a.case:
            self.run_case(a.case, Path(a.out) if a.out else self.RESULTS / f"{slug(a.case)}.json")
        elif a.run_all:
            self.run_all()
        elif a.assemble:
            self.assemble()
        else:
            ap.print_help()
