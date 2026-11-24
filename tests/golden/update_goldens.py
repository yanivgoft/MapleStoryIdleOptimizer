#!/usr/bin/env python3
"""Refresh the golden files from the CURRENT ENGINE, with a reviewable diff.

    python3 tests/golden/update_goldens.py --class hero                       # DRY RUN (default): compact summary, nothing is touched
    python3 tests/golden/update_goldens.py --class hero --kind class          # class | artifacts | sensitivity | all (default)
    python3 tests/golden/update_goldens.py --class all                        # every class
    python3 tests/golden/update_goldens.py --class hero --case "WB/"          # only the cases whose id contains the substring
    python3 tests/golden/update_goldens.py --class hero --write --reason "Raging Blow +1% base damage (user, 2026-12-01)"
    python3 tests/golden/update_goldens.py --class hero --golden-dir /tmp/g   # read / write the golden files of another directory (default: tests/golden)
    python3 tests/golden/update_goldens.py --class all --max-cases 3          # a quick sample: the first 3 cases of every file
    python3 tests/golden/update_goldens.py --class hero --exact               # also rewrite values that are within the test tolerance but not bit-equal
    python3 tests/golden/update_goldens.py --create --class dawn_warrior --reason "first snapshot"    # ENGINE-NATIVE class (no workbook): create <id>_snapshot.json
    python3 tests/golden/update_goldens.py --class dawn_warrior               # ... later: dry-run diff of the snapshot against the current engine, then --write --reason
    python3 tests/golden/update_goldens.py --class native                     # every engine-native class

WHEN: only after a model rule was changed ON PURPOSE in the engine and the failing golden tests are understood.  Never hand-edit a golden JSON, never "fix" a failing
golden by loosening a tolerance: run the dry run, review the summary (which fields moved, by how much), then ``--write --reason "..."``.

HONEST LABELLING: the golden files were frozen from the Excel verify scripts / workbooks (independent implementations).  A refreshed golden PINS THE ENGINE'S OWN
BEHAVIOUR: it is no longer an independent workbook value, only a regression pin of the engine as it was when the refresh was made.  Every ``--write`` therefore
appends one line (date, class, kind, git HEAD, values changed, max relative difference, the required ``--reason``) to ``tests/golden/golden_refresh_log.md``; the
JSON files themselves get no new keys (provenance lives in the log, the files keep their original ``meta`` header untouched).

HOW (no per-class inverse mappings): the existing comparers already map "golden field -> engine value".  Every numeric / string / bool leaf of the golden's compared
part (``out`` of a class golden, ``workbook`` of the artifacts / sensitivity goldens) is replaced by a tracked subclass instance that remembers its JSON path
(``TFloat`` / ``TInt`` / ``TStr`` / ``TBool``); the class's own comparer (``test_<id>.py::compare``, ``ArtifactsTest.compare``, ``sens_compare_generic.compare_case``)
runs unchanged, and every ``chk(name, golden_value, engine_value)`` whose golden value is a tracked leaf yields ``path -> engine value``.  A value is rewritten
when the comparer's OWN check fails (class goldens: any difference, bit-exact; artifacts / sensitivity: outside rel 1e-9 and the comparer's atol); ``--exact`` rewrites
every value that is not bit-equal.  The file is then dumped in the file's own JSON format, so a no-op refresh is byte-identical (checked before every write).

Reported and left alone: golden values the comparer derives arithmetically or compares against a literal ("untracked" - fine while they agree, "unrefreshable" when they
differ), golden leaves no check reads ("unchecked": inputs-like or workbook-only fields), a case the engine can no longer compute (error), two checks that want
different engine values for the same leaf (conflict), differences the comparer reports that are not a leaf check (ranking, ...: "unexplained").

ENGINE-NATIVE classes (``registry.NATIVE``: no workbook, no workbook golden; the Cygnus classes) have ONE file, ``<id>_snapshot.json`` (``snapshot_common.py`` / ``test_snapshots.py``):
generic case matrix -> engine output, every numeric leaf compared.  ``--create`` writes it from the CURRENT engine (REQUIRES --reason; logged as "engine-native snapshot: pins
the engine, no independent source" - there is NO independent source for such a file at all); afterwards the normal dry run / ``--write --reason`` work on it: the matrix and every
output are regenerated, the diff is leaf by leaf (values outside rel 1e-9, cases added / removed), and a write replaces the file (a no-op write leaves it byte-identical:
nothing is written when no value left the tolerance; ``--exact`` also rewrites bit-level drift).

Exit code: 0 = ran (dry run: with or without changes; --write: written), 1 = unrefreshable / unexplained differences or errors remain, 2 = usage / environment.
Needs Python 3.11 and PYTHONHASHSEED=0 (the goldens are bit-exact; the script re-executes itself with the seed set).
"""
import argparse
import contextlib
import copy
import datetime
import importlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
import registry  # noqa: E402
import snapshot_common as SN  # noqa: E402
import factor_mode  # noqa: E402

LOG_NAME = "golden_refresh_log.md"
LOG_HEADER = """# Golden refresh log

Every line below is a refresh of golden JSON files FROM THE CURRENT ENGINE (`python3 tests/golden/update_goldens.py ... --write --reason "..."`).

**A refreshed golden pins the ENGINE's own behaviour.** The goldens were originally frozen from the Excel verify scripts / workbooks (independent implementations
of the model); once a value has been refreshed here it is no longer an independent workbook value, only a regression pin of the engine as it was at the commit in
the table.  Review every refresh like a code change (the dry-run summary shows which fields moved and by how much).  The JSON files carry no refresh marker: this
table is the only provenance.  `HEAD` is the git commit the engine was built on; `+dirty` = uncommitted changes under engine/ at the time.

| date | class | kind | HEAD | cases changed | values changed | max rel diff | reason |
|---|---|---|---|---|---|---|---|
"""
KINDS = registry.KINDS
SNAPSHOT = "snapshot"                                                                            # the one "kind" of an engine-native class
TRACKED_KEYS = {"class": ("out",), "artifacts": ("workbook",), "sensitivity": ("workbook",)}     # the compared part of a case (the rest is copied untouched)
ROOT_PREFIX = {"class": (), "artifacts": ("cases",), "sensitivity": ("cases",), SNAPSHOT: ("cases",)}   # JSON path of the dict of cases
DEFAULT_RTOL = {"class": 0.0, "artifacts": 1e-9, "sensitivity": 1e-9, SNAPSHOT: 1e-9}
NATIVE_LABEL = "engine-native snapshot: pins the engine, no independent source"
MAX_SNAPSHOT_BYTES = 3_000_000


# --------------------------------------------------------------------------- tracked leaves
class TFloat(float):
    pass


class TInt(int):
    pass


class TBool(int):                  # bool cannot be subclassed; compares / formats like 0 / 1, the comparers only ``==`` it
    pass


class TStr(str):
    pass


def track(node, path):
    """A copy of the JSON tree ``node`` whose leaves are tracked instances (``.path`` = the leaf's JSON path); None leaves stay None."""
    if isinstance(node, dict):
        return {k: track(v, path + (k,)) for k, v in node.items()}
    if isinstance(node, list):
        return [track(v, path + (i,)) for i, v in enumerate(node)]
    for typ, wrap in ((bool, TBool), (float, TFloat), (int, TInt), (str, TStr)):       # bool before int
        if isinstance(node, typ):
            leaf = wrap(node)
            leaf.path = path
            return leaf
    return node


def count_leaves(node):
    if isinstance(node, dict):
        return sum(count_leaves(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_leaves(v) for v in node)
    return 0 if node is None else 1


def plain(v):
    """Engine value -> builtin JSON value (tracked / numpy-like scalars and tuples normalised)."""
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, float):
        return float(v)
    if isinstance(v, int):
        return int(v)
    if isinstance(v, str):
        return str(v)
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    return v


def rel_diff(a, b):
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    if a == b:
        return 0.0
    if math.isnan(a) or math.isnan(b) or math.isinf(a) or math.isinf(b):
        return math.inf
    return abs(a - b) / max(abs(a), abs(b))


# --------------------------------------------------------------------------- recording the comparers' checks
class Recorder:
    """Collects (golden value, engine value, ok) of every ``chk`` call: the comparers' equality functions are wrapped (only calls made from a function named
    ``chk`` count - the ranking / tie-break calls of the sensitivity comparer are not golden-vs-engine checks)."""

    def __init__(self):
        self.records = []

    def wrap(self, orig):
        def wrapper(a, b, *args, **kw):
            ok = orig(a, b, *args, **kw)
            if sys._getframe(1).f_code.co_name == "chk":
                self.records.append((a, b, ok))
            return ok
        return wrapper

    @contextlib.contextmanager
    def patched(self):
        import golden_harness as GH
        import artifacts_harness as AH
        import sens_compare_generic as C
        saved = [(GH, "eq", GH.eq), (AH, "close", AH.close), (C, "close", C.close)]
        for mod, name, orig in saved:
            setattr(mod, name, self.wrap(orig))
        try:
            yield self
        finally:
            for mod, name, orig in saved:
                setattr(mod, name, orig)


# --------------------------------------------------------------------------- the three kinds
class KindRunner:
    """One golden kind of one class: file name, how to run a case through the engine + the class's own comparer."""

    def __init__(self, entry, kind):
        self.entry, self.kind = entry, kind
        self.filename = {"class": entry.class_golden, "artifacts": entry.artifacts_golden, "sensitivity": entry.sens_golden}[kind]
        self.rtol = DEFAULT_RTOL[kind]
        self.prefix = ROOT_PREFIX[kind]
        if kind == "class":
            self.mod = importlib.import_module(entry.class_script[:-3])          # test_<id>.py: its own ``compare``
            self.engine = entry.engine()
        elif kind == "artifacts":
            import test_artifacts
            self.test = test_artifacts.make_test(entry.id)
        else:
            import sens_test_common as SC
            self.test = SC.SensTest.from_registry(entry.id)

    def cases(self, golden):
        node = golden
        for k in self.prefix:
            node = node[k]
        return node

    def compare(self, cid, case, inputs):
        """Run the engine on ``inputs`` (a private copy) and the class's own comparer on the tracked ``case``; -> list of (name, golden, engine) differences."""
        if self.kind == "class":
            return self.mod.compare(case, self.engine.compute(inputs), self.rtol)
        if self.kind == "artifacts":
            return self.test.compare(case, self.test.module.compute(inputs), self.rtol)
        import sens_compare_generic as C
        return C.compare_case(self.test.module, cid, case, self.rtol)[1]


# --------------------------------------------------------------------------- one (class, kind) refresh
class Result:
    def __init__(self, cid, kind, filename):
        self.cid, self.kind, self.filename = cid, kind, filename
        self.n_cases = self.n_selected = 0
        self.cases_changed = set()
        self.changes = {}                 # path -> (old, new)
        self.checks = 0
        self.untracked_equal = 0
        self.untracked_differ = []        # (case, name, golden, engine): a check whose golden value is not a leaf (derived / literal) and differs
        self.unexplained = []             # (case, name, golden, engine): a difference that is not a leaf check
        self.conflicts = 0
        self.drift_n = 0                  # tracked leaves inside the test tolerance but not bit-equal (not rewritten unless --exact)
        self.drift_max = 0.0
        self.errors = []                  # (case, message)
        self.leaves = self.seen = 0
        self.nonnumeric_changes = 0
        self.seconds = 0.0
        self.written = False
        self.format = None

    @property
    def max_rel(self):
        rels = [r for r in (rel_diff(o, n) for o, n in self.changes.values()) if r is not None]
        return max(rels) if rels else 0.0

    @property
    def problems(self):
        return len(self.untracked_differ) + len(self.unexplained) + len(self.errors) + self.conflicts


def detect_format(text):
    """The ``json.dumps`` keyword set that reproduces ``text`` byte for byte (class goldens: default; artifacts / sensitivity goldens: indent=0), or None."""
    data = json.loads(text)
    for name, kw in (("default", {}), ("indent=0", {"indent": 0})):
        if json.dumps(data, **kw) == text:
            return name, kw
    return None, None


def set_path(root, path, value):
    node = root
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value


def refresh_one(entry, kind, gdir, only=None, exact=False, write=False, verify=True, max_cases=None):
    """Skill-level growth mode per class: a WORKBOOK class is refreshed in the legacy 300-clamp mode (its goldens are compared in that mode, engine/common/factors.py),
    an engine-native class in the production (extended) mode."""
    with factor_mode.scope(entry.engine_native):
        return _refresh_one(entry, kind, gdir, only, exact, write, verify, max_cases)


def _refresh_one(entry, kind, gdir, only, exact, write, verify, max_cases):
    if kind == SNAPSHOT:
        return refresh_snapshot(entry, gdir, only, exact, write, verify, max_cases)
    runner = KindRunner(entry, kind)
    path = Path(gdir) / runner.filename
    res = Result(entry.id, kind, runner.filename)
    t0 = time.time()
    raw = path.read_bytes().decode("utf-8")
    golden = json.loads(raw)                                  # the tree that gets written
    all_cases = runner.cases(golden)
    res.n_cases = len(all_cases)
    selected = [cid for cid in all_cases if not only or only in cid][:max_cases]
    res.n_selected = len(selected)
    rec = Recorder()
    first = {}                                                # path -> engine value of the first check that wanted a rewrite
    seen = set()
    with rec.patched():
        for cid in selected:
            plain_case = all_cases[cid]
            case = {k: (track(v, runner.prefix + (cid, k)) if k in TRACKED_KEYS[kind] else copy.deepcopy(v)) for k, v in plain_case.items()}
            res.leaves += sum(count_leaves(plain_case[k]) for k in TRACKED_KEYS[kind] if k in plain_case)
            del rec.records[:]
            try:
                diffs = runner.compare(cid, case, copy.deepcopy(plain_case.get("inputs")))
            except Exception as ex:                          # the engine cannot compute the case / the comparer misses a key: left as it is
                res.errors.append((cid, f"{type(ex).__name__}: {ex}"))
                continue
            failed = []
            for a, b, ok in rec.records:
                res.checks += 1
                p = getattr(a, "path", None)
                if p is None:
                    if ok:
                        res.untracked_equal += 1
                    else:
                        failed.append((a, b))
                    continue
                seen.add(p)
                differs = a != b
                if differs and ok:
                    res.drift_n += 1
                    r = rel_diff(a, b)
                    res.drift_max = max(res.drift_max, r if r is not None else 0.0)
                if not ok:
                    failed.append((a, b))
                if (not ok) or (exact and differs):
                    new = plain(b)
                    if p in first:
                        if first[p] != new:
                            res.conflicts += 1
                        continue
                    first[p] = new
                    res.changes[p] = (plain(a), new)
                    res.cases_changed.add(cid)
            # name the failed checks / find the differences that are not leaf checks
            pos = 0
            for name, g, e in diffs:
                for j in range(pos, len(failed)):
                    if failed[j][0] is g and failed[j][1] is e:
                        pos = j + 1
                        if getattr(g, "path", None) is None:
                            res.untracked_differ.append((cid, name, g, e))
                        break
                else:
                    res.unexplained.append((cid, name, g, e))
    res.seen = len(seen)
    res.nonnumeric_changes = sum(1 for o, n in res.changes.values() if rel_diff(o, n) is None)
    if write and res.changes:
        name, kw = detect_format(raw)
        if kw is None:
            raise SystemExit(f"{path.name}: its JSON formatting is not one this tool reproduces byte for byte (default / indent=0): refusing to write")
        res.format = name
        for p, (_old, new) in res.changes.items():
            set_path(golden, p, new)
        path.write_bytes(json.dumps(golden, **kw).encode("utf-8"))
        res.written = True
        if verify:                                            # the rewritten file must now agree with the engine (up to the unrefreshable differences)
            again = refresh_one(entry, kind, gdir, only, exact, write=False, verify=False, max_cases=max_cases)
            res.remaining = len(again.changes)
    res.seconds = time.time() - t0
    return res


# --------------------------------------------------------------------------- engine-native snapshots
def refresh_snapshot(entry, gdir, only=None, exact=False, write=False, verify=True, max_cases=None):
    """The snapshot of an engine-native class against the CURRENT engine: regenerate the case matrix + outputs, diff leaf by leaf (outside rel 1e-9; cases added / removed),
    and with ``write`` replace the file (a partial run - ``only`` / ``max_cases`` - replaces just the selected cases).  Same Result / summary / log as the golden kinds."""
    path = SN.snapshot_path(entry.id, gdir)
    res = Result(entry.id, SNAPSHOT, path.name)
    t0 = time.time()
    if not path.exists():
        res.errors.append(("-", f"no snapshot yet: python3 tests/golden/update_goldens.py --create --class {entry.id} --reason \"...\""))
        res.seconds = time.time() - t0
        return res
    raw = path.read_bytes().decode("utf-8")
    old = json.loads(raw)
    res.n_cases = len(old["cases"])
    rtol = DEFAULT_RTOL[SNAPSHOT]
    now = SN.matrix(entry.id)
    old_ids = [c for c in old["cases"] if not only or only in c]
    if max_cases is not None:
        old_ids = old_ids[:max_cases]
    new_ids = [c for c in now if (not only or only in c) and (max_cases is None or c in old_ids)]
    selected = list(dict.fromkeys(old_ids + new_ids))
    res.n_selected = len(selected)
    res.format = "default"
    try:
        new = SN.generate(entry.id, ids=set(new_ids))
    except Exception as ex:                                   # the engine cannot build the matrix any more: the file is left as it is
        res.errors.append(("-", f"{type(ex).__name__}: {ex}"))
        res.seconds = time.time() - t0
        return res
    res.added = [c for c in new_ids if c not in old["cases"]]
    res.removed = [c for c in old_ids if c not in now]
    for c in selected:
        a, b = old["cases"].get(c), new["cases"].get(c)
        if a is None or b is None:
            res.cases_changed.add(c)
            res.changes[("cases", c)] = ("<case>" if a else None, "<case>" if b else None)
            res.leaves += SN.count_leaves(a) if a else 0
            continue
        res.leaves += SN.count_leaves(a)
        res.seen += SN.count_leaves(a)
        res.checks += SN.count_leaves(a["out"])
        diffs = SN.diff_leaves(a, b, rtol, ("cases", c))
        changed = {p for p, _o, _n in diffs}
        for p, o, n in diffs:
            res.changes[p] = (None if o is SN.MISSING else o, None if n is SN.MISSING else n)
            res.cases_changed.add(c)
        for p, o, n in SN.diff_leaves(a, b, 0.0, ("cases", c)):       # bit-level drift inside the tolerance
            if p not in changed:
                res.drift_n += 1
                r = rel_diff(o, n)
                res.drift_max = max(res.drift_max, r if r is not None else 0.0)
                if exact:
                    res.changes[p] = (o, n)
                    res.cases_changed.add(c)
    res.nonnumeric_changes = sum(1 for o, n in res.changes.values() if rel_diff(o, n) is None)
    if write and res.changes:
        if SN.dumps(old) != raw:
            raise SystemExit(f"{path.name}: its JSON formatting is not the one snapshot_common.dumps writes: refusing to write")
        if only is None and max_cases is None:
            data = new                                        # the whole file is regenerated
        else:                                                 # a partial run replaces just the selected cases
            cases = dict(old["cases"])
            for c in selected:
                if c in new["cases"]:
                    cases[c] = new["cases"][c]
                else:
                    cases.pop(c, None)
            data = dict(meta=SN.meta(entry.id, len(cases)), cases=cases)
        text = SN.dumps(data)
        if len(text.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
            raise SystemExit(f"{path.name} would be {len(text) / 1e6:.1f} MB (limit {MAX_SNAPSHOT_BYTES / 1e6:.0f} MB): trim the case matrix in snapshot_common.py")
        path.write_bytes(text.encode("utf-8"))
        res.written = True
        if verify:
            again = refresh_snapshot(entry, gdir, only, exact, write=False, verify=False, max_cases=max_cases)
            res.remaining = len(again.changes)
    res.seconds = time.time() - t0
    return res


def create_snapshot(entry, gdir, reason, head):
    """``--create``: write ``<id>_snapshot.json`` from the CURRENT engine and log it; returns the process exit code."""
    path = SN.snapshot_path(entry.id, gdir)
    if path.exists():
        print(f"{path.name} already exists: refresh it with  update_goldens.py --class {entry.id}  (dry run) and then  --write --reason \"...\"")
        return 2
    t0 = time.time()
    with factor_mode.scope(True):                  # engine-native: production (extended) growth curves
        data = SN.generate(entry.id)
    text = SN.dumps(data)
    size = len(text.encode("utf-8"))
    if size > MAX_SNAPSHOT_BYTES:
        print(f"{path.name} would be {size / 1e6:.1f} MB (limit {MAX_SNAPSHOT_BYTES / 1e6:.0f} MB): trim the case matrix in snapshot_common.py; nothing written")
        return 1
    path.write_bytes(text.encode("utf-8"))
    kinds = {}
    for cid_, c in data["cases"].items():
        k = kinds.setdefault(cid_.split("/")[0], [0, 0])
        k[0] += 1
        k[1] += SN.count_leaves(c["out"])
    leaves = sum(v[1] for v in kinds.values())
    print(f"{entry.id}/snapshot  [{path.name}]  CREATED from the current engine | {len(data['cases'])} cases, {leaves} output leaves, {size / 1e6:.2f} MB | {time.time() - t0:.1f}s")
    print("    " + ", ".join(f"{k}: {n} cases / {lv} leaves" for k, (n, lv) in kinds.items()))
    print(f"    {NATIVE_LABEL}: the file is a regression pin of THIS engine, review the numbers against the game before trusting them")
    res = Result(entry.id, SNAPSHOT, path.name)
    res.cases_changed = set(data["cases"])
    res.written = True
    res.n_cases = res.n_selected = len(data["cases"])
    res.changes = {("cases", c): (None, "<case>") for c in data["cases"]}
    res.reason_prefix = "CREATED; "
    log = append_log(gdir, res, reason, head)
    print(f"log: {log}")
    return 0


# --------------------------------------------------------------------------- reporting
def fmt(v, n=24):
    s = repr(v)
    return s if len(s) <= n else s[:n - 1] + "~"


def summarize(res, top=10, verbose=False):
    lines = []
    sel = f"{res.n_selected}/{res.n_cases}" if res.n_selected != res.n_cases else f"{res.n_cases}"
    rel = res.max_rel
    head = (f"{res.cid}/{res.kind}  [{res.filename}]  cases {sel}, changed {len(res.cases_changed)} | values changed {len(res.changes)} "
            f"(of {res.checks} checks) | max rel diff {rel:.3e}" + (f" | non-numeric changes {res.nonnumeric_changes}" if res.nonnumeric_changes else ""))
    lines.append(head)
    lines.append(f"    untracked checks: {res.untracked_equal + len(res.untracked_differ)} ({len(res.untracked_differ)} differing) | unchecked golden leaves: "
                 f"{res.leaves - res.seen}/{res.leaves} | within-tolerance drift (not rewritten): {res.drift_n}" + (f" max {res.drift_max:.1e}" if res.drift_n else "")
                 + f" | {res.seconds:.1f}s")
    fields = {}
    n_prefix = len(ROOT_PREFIX[res.kind]) + 1                 # (cases,) cid  -> field = the rest of the path
    for p, (old, new) in res.changes.items():
        f = "/".join(str(x) for x in p[n_prefix:]) or "(whole case added / removed)"
        e = fields.setdefault(f, {"n": 0, "max": -1.0, "ex": None})
        e["n"] += 1
        r = rel_diff(old, new)
        r = math.inf if r is None else r
        if r > e["max"]:
            e["max"], e["ex"] = r, (p[n_prefix - 1], old, new)
    ranked = sorted(fields.items(), key=lambda kv: (-kv[1]["max"], -kv[1]["n"], kv[0]))
    for f, e in ranked[:top]:
        cid, old, new = e["ex"]
        lines.append(f"    {f}  x{e['n']}  max rel {e['max']:.2e}  e.g. [{cid}] {fmt(old)} -> {fmt(new)}")
    if len(ranked) > top:
        lines.append(f"    ... {len(ranked) - top} more changed field name(s) ({len(fields)} in all)")
    if verbose and res.cases_changed:
        ids = sorted(res.cases_changed)
        lines.append("    changed cases: " + ", ".join(ids[:15]) + (f" ... (+{len(ids) - 15})" if len(ids) > 15 else ""))
    for label, items in (("UNREFRESHABLE (golden value is a literal / derived, differs)", res.untracked_differ), ("UNEXPLAINED (not a leaf check)", res.unexplained)):
        for cid, name, g, e in items[:5]:
            lines.append(f"    {label}: [{cid}] {name}: golden {fmt(g)} engine {fmt(e)}")
        if len(items) > 5:
            lines.append(f"    ... {len(items) - 5} more {label.split(' ')[0].lower()}")
    if getattr(res, "added", None):
        lines.append(f"    cases ADDED to the matrix ({len(res.added)}): " + ", ".join(res.added[:6]) + (" ..." if len(res.added) > 6 else ""))
    if getattr(res, "removed", None):
        lines.append(f"    cases no longer generated ({len(res.removed)}): " + ", ".join(res.removed[:6]) + (" ..." if len(res.removed) > 6 else ""))
    if res.kind == SNAPSHOT and (res.changes or res.written):
        lines.append(f"    {NATIVE_LABEL}")
    for cid, msg in res.errors[:5]:
        lines.append(f"    ERROR [{cid}] {msg[:150]}")
    if len(res.errors) > 5:
        lines.append(f"    ... {len(res.errors) - 5} more error(s)")
    if res.conflicts:
        lines.append(f"    CONFLICT: {res.conflicts} leaf/leaves wanted two different engine values (the first one is used)")
    if res.written:
        rem = getattr(res, "remaining", None)
        lines.append(f"    WRITTEN {res.filename} ({res.format}); re-check against the engine: " + ("n/a" if rem is None else f"{rem} value(s) still differ"))
    return lines


def verdict(results, write):
    n_changed = sum(len(r.changes) for r in results)
    problems = sum(r.problems for r in results)
    if n_changed == 0 and problems == 0:
        return "VERDICT: no change - every golden value already agrees with the engine" + (" (nothing written)" if write else "")
    parts = []
    if n_changed:
        parts.append(f"{n_changed} value(s) in {sum(1 for r in results if r.changes)} file(s) " + ("rewritten from the engine (the goldens now pin the ENGINE's behaviour)"
                                                                                                 if write else "would change: review, then re-run with --write --reason \"...\""))
    if problems:
        parts.append(f"{problems} problem(s) the tool cannot refresh (literal / derived checks, errors, conflicts)")
    return "VERDICT: " + "; ".join(parts)


def git_head():
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=20).stdout.strip() or "unknown"
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "engine"], cwd=REPO, capture_output=True, text=True, timeout=20).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def append_log(gdir, res, reason, head):
    log = Path(gdir) / LOG_NAME
    if not log.exists():
        log.write_text(LOG_HEADER)
    reason = " ".join(reason.split()).replace("|", "/")
    if res.kind == SNAPSHOT:
        reason = f"{NATIVE_LABEL}; {getattr(res, 'reason_prefix', '')}{reason}"
    line = (f"| {datetime.date.today().isoformat()} | {res.cid} | {res.kind} | {head} | {len(res.cases_changed)} | {len(res.changes)} | {res.max_rel:.3e} | {reason} |\n")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return log


# --------------------------------------------------------------------------- command line
def build_parser():
    ap = argparse.ArgumentParser(prog="update_goldens.py", description=__doc__.split("\n\n")[0] + "  Dry run unless --write.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", required=True, choices=list(registry.ALL) + ["all", "native"],
                    help="class id, 'all' (every workbook class) or 'native' (every engine-native class: no workbook, one <id>_snapshot.json each)")
    ap.add_argument("--kind", default="all", choices=list(KINDS) + [SNAPSHOT, "all"],
                    help="which golden file(s) of the class (default all three; an engine-native class has only 'snapshot')")
    ap.add_argument("--create", action="store_true", help="ENGINE-NATIVE class only: create <id>_snapshot.json from the current engine (needs --reason; refuses to overwrite)")
    ap.add_argument("--write", action="store_true", help="rewrite the golden JSON file(s) in place + append a line to golden_refresh_log.md (default: dry run)")
    ap.add_argument("--reason", help="REQUIRED with --write: one line for the log (why the model changed)")
    ap.add_argument("--case", help="only the golden cases whose id contains this substring")
    ap.add_argument("--max-cases", type=int, help="only the first N (selected) cases of every file: a quick sample")
    ap.add_argument("--golden-dir", default=str(HERE), help="directory of the golden files and of the log (default: tests/golden)")
    ap.add_argument("--exact", action="store_true", help="also rewrite values that are within the test tolerance but not bit-equal to the engine")
    ap.add_argument("--fields", type=int, default=10, help="how many changed field names to list per file (default 10)")
    ap.add_argument("-v", "--verbose", action="store_true", help="also list the changed case ids")
    ap.add_argument("--allow-any-python", action="store_true")
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if (a.write or a.create) and not (a.reason and a.reason.strip()):
        ap.error(f"--{'create' if a.create else 'write'} needs --reason \"why\" (it goes into golden_refresh_log.md)")
    if a.create and a.write:
        ap.error("--create writes a NEW snapshot; --write refreshes an existing one: use one of them")
    if a.create and (a.cls in ("all", "native") or not registry.ALL[a.cls].engine_native):
        ap.error("--create needs one ENGINE-NATIVE class id (--class <id>): the workbook classes' goldens come from their workbooks, not from the engine")
    if a.reason and not (a.write or a.create):
        print("note: --reason is only used with --write (this is a dry run)")
    if sys.version_info[:2] != (3, 11) and not a.allow_any_python:
        print(f"ENV: need Python 3.11 (this is {sys.version_info.major}.{sys.version_info.minor}): the goldens depend on 3.11's sum() rounding (or --allow-any-python).")
        return 2
    gdir = Path(a.golden_dir)
    if not gdir.is_dir():
        print(f"golden dir not found: {gdir}")
        return 2
    classes = list(registry.CLASSES) if a.cls == "all" else list(registry.NATIVE) if a.cls == "native" else [a.cls]
    if a.cls == "native" and not a.create:        # an UNPUBLISHED class without a snapshot has nothing to refresh (name it with --class <id> for the --create hint)
        for cid in [c for c in classes if not registry.ALL[c].published and not SN.snapshot_path(c, gdir).exists()]:
            print(f"{cid}: unpublished: no snapshot required (skipped)")
            classes.remove(cid)
    if a.create:
        print(f"update_goldens: CREATE | golden dir {gdir} | {a.cls} (engine-native)")
        return create_snapshot(registry.ALL[a.cls], gdir, a.reason, git_head())
    if a.cls == "native" and not classes:
        print("no engine-native class registered (every engine/classes/<id>.py that is not a workbook class is one)")
        return 0

    def kinds_of(cid):
        native = registry.ALL[cid].engine_native
        if a.kind == "all":
            return [SNAPSHOT] if native else list(KINDS)
        if (a.kind == SNAPSHOT) != native:
            ap.error(f"--kind {a.kind} does not apply to {cid} ({'an engine-native class has only the snapshot' if native else 'a workbook class has no snapshot'})")
        return [a.kind]
    mode = "WRITE" if a.write else "DRY RUN (nothing is touched; add --write --reason \"...\" to rewrite)"
    per_class = {len(kinds_of(c)) for c in classes}
    n_kinds = f"{len(classes)} class(es) x {per_class.pop()} kind(s)" if len(per_class) == 1 else f"{len(classes)} class(es), {sum(len(kinds_of(c)) for c in classes)} file(s)"
    print(f"update_goldens: {mode} | golden dir {gdir} | {n_kinds}" + (f" | cases containing {a.case!r}" if a.case else "") + (f" | first {a.max_cases} case(s)" if a.max_cases else "")
          + (" | --exact" if a.exact else ""))
    results = []
    head = git_head()
    for cid in classes:
        for kind in kinds_of(cid):
            res = refresh_one(registry.ALL[cid], kind, gdir, a.case, a.exact, a.write, max_cases=a.max_cases)
            results.append(res)
            print("\n".join(summarize(res, a.fields, a.verbose)), flush=True)
            if res.written:
                append_log(gdir, res, a.reason, head)
    print(verdict(results, a.write))
    if a.write and any(r.written for r in results):
        print(f"log: {Path(gdir) / LOG_NAME}")
    return 1 if any(r.problems for r in results) else 0


def ensure_env():
    """Re-execute with PYTHONHASHSEED=0 (the goldens are bit-exact against verify scripts that summed over sets under seed 0)."""
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.environ["PYTHONHASHSEED"] = "0"
        os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    ensure_env()
    sys.exit(main())
