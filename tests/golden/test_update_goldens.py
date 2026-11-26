#!/usr/bin/env python3
"""Tests of ``update_goldens.py`` (the tool that refreshes the golden JSON files from the current engine).  Plain ``python3`` runnable, also pytest-collectable; ~10 s.
Never writes into the real tests/golden: every write goes to a temporary copy (``--golden-dir``).

  (a) a no-op dry run on EVERY class and kind (the first case of every file) reports 0 changed; a ``--write`` run against a copy of the golden dir leaves every file
      byte-identical (and writes no log line); every golden file's JSON formatting is one the tool reproduces byte for byte
  (b) a golden value changed by 1e-6 (relative) in a copy -> the dry run reports exactly that field; ``--write`` fixes it (class golden: byte-identical to the
      original again), logs it, and the golden's own test entry point against the copy passes again
  (c) ``--write`` without ``--reason`` is refused; the help / the log header carry the "pins the ENGINE's behaviour" label
  (d) ENGINE-NATIVE classes (no workbook; one ``<id>_snapshot.json``): ``--create`` (needs --reason, refuses to overwrite, logs the "no independent source" label), a no-op
      refresh is byte-identical, a changed engine (a tampered stored value / a removed / an extra case) shows in the dry run and ``--write`` restores the file byte for byte,
      ``test_snapshots`` agrees.  Hero stands in for a native class (registry override), always in a temporary directory.
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import registry  # noqa: E402
import snapshot_common as SN  # noqa: E402
import update_goldens as U  # noqa: E402
import factor_mode  # noqa: E402
from engine.common import factors  # noqa: E402

FACTOR_MODE = factor_mode.pin("legacy")        # hero & co. are workbook classes here (the hero-as-native test switches to extended inside its own context)

TAMPER = 1e-6


def golden_files(cid=None):
    ids = [cid] if cid else list(registry.CLASSES)
    return [HERE / name for i in ids for name in (registry.CLASSES[i].class_golden, registry.CLASSES[i].artifacts_golden, registry.CLASSES[i].sens_golden)]


@contextlib.contextmanager
def copy_of(cid=None):
    """A temporary directory holding copies of the golden files (of one class, or all)."""
    with tempfile.TemporaryDirectory(prefix="goldens_") as tmp:
        for f in golden_files(cid):
            shutil.copy2(f, tmp)
        yield Path(tmp)


def run_main(*argv):
    """(exit code, stdout) of ``update_goldens.main(argv)``."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        rc = U.main(list(argv))
    return rc, out.getvalue()


def test_noop_dry_run_and_write_every_class_and_kind():
    with copy_of() as gdir:
        before = {f.name: f.read_bytes() for f in gdir.glob("*.json")}
        assert len(before) == 3 * len(registry.CLASSES)
        for cid, entry in registry.CLASSES.items():
            for kind in registry.KINDS:
                res = U.refresh_one(entry, kind, gdir, write=True, max_cases=1)      # --write on an up-to-date file: nothing to write
                assert res.n_selected == 1 and res.checks > 0, (cid, kind)
                assert not res.changes and not res.cases_changed and not res.written, (cid, kind, list(res.changes)[:3])
                assert res.problems == 0, (cid, kind, res.untracked_differ[:2], res.unexplained[:2], res.errors[:2], res.conflicts)
                assert res.untracked_equal < res.checks // 2, (cid, kind)               # (the golden leaves are tracked; only {} / None / bool() / `or 0.0` checks are not)
        after = {f.name: f.read_bytes() for f in gdir.glob("*.json")}
        assert after == before, "a no-op --write changed a golden file"
        assert not (gdir / U.LOG_NAME).exists(), "a no-op --write logged a refresh"
        for name, raw in before.items():                                                # every file's format is reproduced byte for byte (so a refresh only changes values)
            assert U.detect_format(raw.decode("utf-8"))[1] is not None, f"{name}: JSON formatting not reproducible by update_goldens"
        rc, text = run_main("--class", "hero", "--max-cases", "1", "--golden-dir", str(gdir))      # the command line, dry run
        assert rc == 0 and "DRY RUN" in text and "VERDICT: no change" in text, text


def _tamper(raw, cid, path):
    """The file text with the number at ``path`` of case ``cid`` multiplied by (1 + 1e-6), in the file's own JSON format; -> (new text, old value, new value)."""
    fmt, kw = U.detect_format(raw)
    data = json.loads(raw)
    node = data
    for k in path[:-1]:
        node = node[k]
    old = node[path[-1]]
    node[path[-1]] = old * (1 + TAMPER)
    return json.dumps(data, **kw), old, node[path[-1]]


def test_tampered_value_is_reported_and_fixed():
    import golden_harness as GH
    import sens_test_common as SC
    import test_artifacts
    entry = registry.CLASSES["hero"]
    mod = U.importlib.import_module(entry.class_script[:-3])
    with copy_of("hero") as gdir:
        pristine = {f.name: f.read_bytes() for f in gdir.glob("*.json")}
        cases = {}
        for kind in registry.KINDS:                       # (a case, the path of a value its own comparer checks)
            r = U.KindRunner(entry, kind)
            golden = json.loads((gdir / r.filename).read_text())
            cid = next(iter(r.cases(golden)))
            cases[kind] = (cid, r.prefix + (cid, "out", "total_dps") if kind == "class" else
                           r.prefix + (cid, "workbook", "total_dps") if kind == "artifacts" else r.prefix + (cid, "workbook", "summary", "total"))
        olds = {}
        for kind, (cid, path) in cases.items():
            f = gdir / U.KindRunner(entry, kind).filename
            text, old, new = _tamper(f.read_text(), cid, path)
            f.write_bytes(text.encode("utf-8"))
            olds[kind] = (old, new)
            res = U.refresh_one(entry, kind, gdir, only=cid, max_cases=1)
            assert list(res.changes) == [path] and res.problems == 0, (kind, list(res.changes), res.problems)      # exactly that field
            assert res.changes[path][0] == new and abs(res.changes[path][1] - old) <= 1e-9 * abs(old), (kind, res.changes[path], old)
            assert res.cases_changed == {cid} and 0 < res.max_rel < 2 * TAMPER, (kind, res.max_rel)
            # dry run changes nothing on disk
            assert (gdir / res.filename).read_bytes() == text.encode("utf-8")
        rc, text = run_main("--class", "hero", "--max-cases", "1", "--golden-dir", str(gdir))                 # the CLI dry run names the fields
        assert rc == 0 and "total_dps" in text and "would change" in text and "3 value(s) in 3 file(s)" in text, text
        rc, text = run_main("--class", "hero", "--max-cases", "1", "--write", "--reason", "unit test: tampered value", "--golden-dir", str(gdir))
        assert rc == 0 and text.count("WRITTEN") == 3 and "0 value(s) still differ" in text, text
        # fixed: class golden is byte-identical to the original again (the engine reproduces it bit-exactly); the others pass their own entry point
        assert (gdir / entry.class_golden).read_bytes() == pristine[entry.class_golden]
        n, bad = GH.run_golden(entry.engine(), gdir / entry.class_golden, mod.compare, 0.0, False)
        assert n > 0 and not bad
        t = test_artifacts.make_test("hero")
        t.GOLDEN = gdir / entry.artifacts_golden
        n, bad, toggles = t.run(1e-9)
        assert n > 0 and not bad and all(x[3] for x in toggles) and all(e[5] for e in t.equiv), bad
        st = SC.SensTest.from_registry("hero")
        st.GOLDEN = gdir / entry.sens_golden
        n_cases, n_values, bad = st.run_golden(1e-9, False, None)
        assert n_cases > 0 and not bad, bad
        for kind in ("artifacts", "sensitivity"):         # only the tampered leaf moved
            a, b = json.loads(pristine[U.KindRunner(entry, kind).filename]), json.loads((gdir / U.KindRunner(entry, kind).filename).read_bytes())
            assert a["meta"] == b["meta"]        # (the refreshed leaf is the engine's bit value: it equals the pristine file when that was itself refreshed from the engine, as hero's was on 2026-11-26)
        # the log: one line per refreshed file, with the honest header
        log = (gdir / U.LOG_NAME).read_text()
        assert "pins the ENGINE" in log and log.count("unit test: tampered value") == 3 and "| hero | sensitivity |" in log, log
        # and a second refresh is a no-op again
        rc, text = run_main("--class", "hero", "--max-cases", "1", "--golden-dir", str(gdir))
        assert "VERDICT: no change" in text, text


def test_write_requires_reason():
    with copy_of("hero") as gdir:
        before = {f.name: f.read_bytes() for f in gdir.glob("*.json")}
        for extra in ([], ["--reason", "   "]):
            try:
                run_main("--class", "hero", "--write", "--golden-dir", str(gdir), *extra)
            except SystemExit as ex:
                assert ex.code == 2
            else:
                raise AssertionError("--write without a reason must be refused")
        assert {f.name: f.read_bytes() for f in gdir.glob("*.json")} == before and not (gdir / U.LOG_NAME).exists()
    assert "pins the engine" in U.build_parser().format_help().lower() and "pins the ENGINE" in U.LOG_HEADER


@contextlib.contextmanager
def hero_as_native():
    """Hero registered as an engine-native class (the registry's own ``MSI_NATIVE_CLASSES`` mechanism, applied in-process and undone afterwards)."""
    entry = registry.native_entry("hero", "Hero")
    saved = dict(registry.NATIVE), dict(registry.ALL)
    registry.NATIVE["hero"] = registry.ALL["hero"] = entry
    prev = factors.legacy_clamp_enabled()
    factors.set_legacy_clamp(False)          # a native class runs in production mode (update_goldens / test_snapshots do the same for it); the rest of this module is legacy
    try:
        yield entry
    finally:
        factors.set_legacy_clamp(prev)
        registry.NATIVE.clear()
        registry.NATIVE.update(saved[0])
        registry.ALL.clear()
        registry.ALL.update(saved[1])


def test_engine_native_snapshot_create_refresh_and_noop():
    with factors.legacy_clamp(True):                 # (importing test_snapshots pins the extended mode; this module stays legacy)
        import test_snapshots as TS
    with tempfile.TemporaryDirectory(prefix="snap_") as tmp, hero_as_native() as entry:
        gdir = Path(tmp)
        jobs = dict(registry.all_jobs("hero"))
        assert jobs == {"hero:snapshot": ["test_snapshots.py", "--class", "hero"], "hero:engine": ["test_engine_native.py", "--class", "hero"]}, jobs
        path = gdir / entry.snapshot
        # --create needs a reason, one engine-native class, and refuses to overwrite
        for argv in (["--create", "--class", "hero"], ["--create", "--class", "native", "--reason", "x"], ["--create", "--write", "--class", "hero", "--reason", "x"]):
            try:
                run_main(*argv, "--golden-dir", str(gdir))
            except SystemExit as ex:
                assert ex.code == 2, argv
            else:
                raise AssertionError(f"{argv} must be refused")
        rc, text = run_main("--class", "hero", "--golden-dir", str(gdir))                      # a dry run before --create: a problem, nothing created
        assert rc == 1 and "no snapshot yet" in text and not path.exists(), text
        rc, text = run_main("--create", "--class", "hero", "--reason", "unit test: create", "--golden-dir", str(gdir))
        assert rc == 0 and path.exists() and "CREATED" in text and "no independent source" in text, text
        pristine = path.read_bytes()
        assert 0 < len(pristine) < 3_000_000 and SN.dumps(json.loads(pristine)).encode("utf-8") == pristine
        log = (gdir / U.LOG_NAME).read_text()
        assert "pins the ENGINE" in log and "engine-native snapshot: pins the engine, no independent source; CREATED; unit test: create" in log and "| hero | snapshot |" in log, log
        rc, text = run_main("--create", "--class", "hero", "--reason", "again", "--golden-dir", str(gdir))
        assert rc == 2 and "already exists" in text and path.read_bytes() == pristine
        # the snapshot test passes on the fresh file and the case matrix is current
        n, leaves, bad = TS.compare_snapshot("hero", gdir=gdir)
        assert n == len(json.loads(pristine)["cases"]) > 300 and leaves > 10_000 and not bad
        assert TS.matrix_problems("hero", gdir) == ([], [])
        # no-op: dry run and --write leave the file byte-identical and log nothing
        rc, text = run_main("--class", "hero", "--golden-dir", str(gdir))
        assert rc == 0 and "VERDICT: no change" in text and path.read_bytes() == pristine, text
        rc, text = run_main("--class", "hero", "--write", "--reason", "noop", "--golden-dir", str(gdir))
        assert rc == 0 and "nothing written" in text and path.read_bytes() == pristine and log == (gdir / U.LOG_NAME).read_text(), text
        # a changed engine = a stored file that differs: a tampered value, a case the engine no longer generates, a case missing from the file
        data = json.loads(pristine)
        data["cases"]["M/World Boss/late/comp"]["out"]["total_dps"] *= 1 + TAMPER
        data["cases"]["L/World Boss/nocomp/100"]["out"]["skills"][0]["dps"] *= 2
        data["cases"]["ZZ/obsolete"] = data["cases"]["A/candle"]
        del data["cases"]["A/pigs_ribbon"]
        path.write_bytes(SN.dumps(data).encode("utf-8"))
        tampered = path.read_bytes()
        n, leaves, bad = TS.compare_snapshot("hero", gdir=gdir)
        assert set(bad) >= {"M/World Boss/late/comp", "L/World Boss/nocomp/100"} and TS.matrix_problems("hero", gdir) == (["A/pigs_ribbon"], ["ZZ/obsolete"])
        rc, text = run_main("--class", "hero", "--golden-dir", str(gdir))
        assert rc == 0 and "would change" in text and "total_dps" in text and "skills/0/dps" in text and "A/pigs_ribbon" in text and "ZZ/obsolete" in text, text
        assert path.read_bytes() == tampered                                                    # a dry run touches nothing
        rc, text = run_main("--class", "hero", "--case", "M/World Boss/late/comp", "--golden-dir", str(gdir))      # --case: only that case is looked at
        assert "values changed 1 " in text and "skills/0/dps" not in text and "ZZ/obsolete" not in text, text
        rc, text = run_main("--class", "hero", "--write", "--reason", "unit test: refresh", "--golden-dir", str(gdir))
        assert rc == 0 and "WRITTEN" in text and "0 value(s) still differ" in text, text
        assert path.read_bytes() == pristine                                                    # the engine reproduces the original: byte-identical again
        log = (gdir / U.LOG_NAME).read_text()
        assert log.count("| hero | snapshot |") == 2 and "unit test: refresh" in log and "engine-native snapshot" in log.splitlines()[-1], log
        # a partial --write (one case) rewrites just that case
        data = json.loads(pristine)
        data["cases"]["M/World Boss/late/comp"]["out"]["total_dps"] *= 1 + TAMPER
        data["cases"]["A/candle"]["out"]["total_dps"] *= 1 + TAMPER
        path.write_bytes(SN.dumps(data).encode("utf-8"))
        rc, text = run_main("--class", "hero", "--case", "M/World Boss/late/comp", "--write", "--reason", "partial", "--golden-dir", str(gdir))
        assert rc == 0 and "WRITTEN" in text
        again = json.loads(path.read_bytes())
        assert again["cases"]["M/World Boss/late/comp"] == json.loads(pristine)["cases"]["M/World Boss/late/comp"] and again["cases"]["A/candle"] == data["cases"]["A/candle"]
    # outside the stand-in hero is a workbook class: --create is refused for it
    try:
        run_main("--create", "--class", "hero", "--reason", "x")
    except SystemExit as ex:
        assert ex.code == 2
    else:
        raise AssertionError("--create must refuse a workbook class")


def test_registry_has_no_native_entry_for_workbook_classes():
    assert all(not e.engine_native for e in registry.CLASSES.values()) and all(e.engine_native for e in registry.NATIVE.values())
    assert set(registry.ALL) == set(registry.CLASSES) | set(registry.NATIVE)


if __name__ == "__main__":
    import time
    for name, fn in sorted((n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)):
        t0 = time.time()
        fn()
        print(f"ok {name} ({time.time() - t0:.1f}s)")
    print("OK: update_goldens no-op dry run / write, tampered value reported + fixed, --write needs --reason, engine-native snapshot create / refresh / no-op")
