#!/usr/bin/env python3
"""Tests of the golden-side PUBLISH GATE (engine classes that export ``PUBLISHED = False``).  Plain ``python3`` runnable, also pytest-collectable; < 2 s, writes nothing into the repo.

  (a) ``registry.is_published_source`` reads ``PUBLISHED = False`` from a class module's source (a comment / ``PUBLISHED = True`` / no attribute / no file = published)
  (b) an UNPUBLISHED engine-native class without a snapshot file: its snapshot job is skipped (``skipped_jobs`` says "unpublished: no snapshot required"), ``test_engine_native.py`` still runs,
      ``registry.check()`` does not complain, ``test_snapshots.main`` prints the note and exits 0; once the snapshot file exists it is a normal job again; a PUBLISHED native class still REQUIRES it
  (c) ``run_all.child_env`` / ``run_all.run`` hand ``MSI_INCLUDE_UNPUBLISHED=1`` + ``PYTHONHASHSEED=0`` to every subprocess (the API pytest, golden jobs and web group all go through ``run``)
  (d) ``web/scripts/gen_fixtures.py``: without ``--include-unpublished`` the API app is created with the variable REMOVED (even if the shell exports it), with the flag it is set to 1
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests"))
import registry  # noqa: E402
import run_all  # noqa: E402

ENV_VAR = "MSI_INCLUDE_UNPUBLISHED"


def fake_native(cid, tmp, published_line, snapshot=False):
    """Register a fake engine-native class ``cid`` whose module source is in ``tmp`` (registry.REPO / HERE patched by the caller)."""
    src = Path(tmp) / "engine" / "classes"
    src.mkdir(parents=True, exist_ok=True)
    (src / f"{cid}.py").write_text(f'{published_line}\nCLASS_NAME = "Fake"\n')
    if snapshot:
        (Path(tmp) / f"{cid}_snapshot.json").write_text("{}")
    return registry.native_entry(cid)


@contextlib.contextmanager
def patched_registry(tmp, *entries):
    """The registry as if ``entries`` were discovered engine-native classes living under ``tmp`` (REPO for the module source, HERE for the snapshot files)."""
    native = {e.id: e for e in entries}
    with mock.patch.object(registry, "REPO", Path(tmp)), mock.patch.object(registry, "HERE", Path(tmp)), \
            mock.patch.object(registry, "NATIVE", native), mock.patch.object(registry, "ALL", {**registry.CLASSES, **native}):
        yield


def test_is_published_source():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(registry, "REPO", Path(tmp)):
        d = Path(tmp) / "engine" / "classes"
        d.mkdir(parents=True)
        cases = {"a_false": ("PUBLISHED = False\n", False), "a_spaced": ("PUBLISHED   =   False  # wip\n", False), "a_typed": ("PUBLISHED: bool = False\n", False),
                 "b_true": ("PUBLISHED = True\n", True), "c_none": ("CLASS_NAME = 'x'\n", True), "d_comment": ("# PUBLISHED = False once ready\nCLASS_NAME = 'x'\n", True),
                 "e_indented": ("def f():\n    PUBLISHED = False\n", True)}
        for cid, (src, _) in cases.items():
            (d / f"{cid}.py").write_text(src)
        for cid, (_, expect) in cases.items():
            assert registry.is_published_source(cid) is expect, cid
        assert registry.is_published_source("no_such_file") is True


def test_unpublished_native_class_needs_no_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(registry, "REPO", Path(tmp)), mock.patch.object(registry, "HERE", Path(tmp)):
            unpub = fake_native("zz_unpub", tmp, "PUBLISHED = False")
            pub = fake_native("zz_pub", tmp, "CLASS_ID = 'zz_pub'")
        with patched_registry(tmp, unpub, pub):
            assert not unpub.published and pub.published
            assert unpub.snapshot_optional and not pub.snapshot_optional
            assert [k for k, _ in unpub.jobs()] == ["engine"]                       # test_engine_native still runs, the snapshot job is skipped
            assert [k for k, _ in pub.jobs()] == ["snapshot", "engine"]            # a published native class still requires its snapshot
            assert ("zz_unpub:snapshot", "unpublished: no snapshot required") in registry.skipped_jobs()
            assert not any(label.startswith("zz_pub") for label, _ in registry.skipped_jobs())
            labels = [label for label, _ in registry.all_jobs()]
            assert "zz_unpub:engine" in labels and "zz_unpub:snapshot" not in labels and "zz_pub:snapshot" in labels
            problems = registry.check()
            assert not any("zz_unpub" in p and "snapshot" in p for p in problems)   # (the other missing engine/data files of the fake are not the point)
            assert any("zz_pub" in p and "snapshot" in p for p in problems)
            import test_snapshots
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = test_snapshots.main(["--class", "zz_unpub"])
            assert rc == 0 and "unpublished: no snapshot required" in out.getvalue()
            # once the file exists it is compared / required like any other class
            (Path(tmp) / "zz_unpub_snapshot.json").write_text("{}")
            assert not unpub.snapshot_optional and [k for k, _ in unpub.jobs()] == ["snapshot", "engine"]
            assert not any(label == "zz_unpub:snapshot" for label, _ in registry.skipped_jobs())


def test_real_native_classes_are_published_and_keep_their_snapshot_job():
    assert registry.NATIVE, "expected at least dawn_warrior"
    for cid, e in registry.NATIVE.items():
        if e.published:
            assert [k for k, _ in e.jobs()][0] == "snapshot", cid
    assert all(e.published for e in registry.CLASSES.values())


def test_run_all_env_propagation():
    env = run_all.child_env(base={"PATH": "/bin", "KEEP": "1"})
    assert env[ENV_VAR] == "1" and env["PYTHONHASHSEED"] == "0" and env["KEEP"] == "1"
    assert run_all.child_env(base={ENV_VAR: "0", "PYTHONHASHSEED": "random"})[ENV_VAR] == "1"       # a stray value is overridden
    assert run_all.child_env({"X": "2"}, base={})["X"] == "2"
    # the real thing: a subprocess started through run_all.run sees both variables (every job, pytest chunk and the web group go through run)
    rc, out, _ = run_all.run([sys.executable, "-c", "import os; print(os.environ.get('MSI_INCLUDE_UNPUBLISHED'), os.environ.get('PYTHONHASHSEED'))"])
    assert rc == 0 and out.split() == ["1", "0"], out
    src = Path(run_all.__file__).read_text()
    assert "subprocess.run(" in src and src.count("subprocess.run(") == 1                          # one launcher: nothing bypasses child_env


def test_gen_fixtures_gate_flag():
    script = (
        "import os, sys, json\n"
        f"sys.path.insert(0, {str(ROOT / 'web' / 'scripts')!r})\n"
        "import gen_fixtures as G\n"
        "class Stop(Exception): pass\n"
        "def fake_create_app(*a, **k): raise Stop(os.environ.get('MSI_INCLUDE_UNPUBLISHED', 'unset'))\n"
        "G.create_app = fake_create_app\n"
        "sys.argv = ['gen_fixtures.py'] + sys.argv[1:]\n"
        "try:\n    G.main()\nexcept Stop as ex:\n    print('ENV=' + str(ex))\n")
    py = ROOT / ".venv" / "bin" / "python"
    if not py.exists():
        return                                                                                   # (needs fastapi, which lives in the venv)
    for args, shell_value, expect in (([], "1", "unset"), ([], None, "unset"), (["--include-unpublished"], None, "1")):
        env = {k: v for k, v in os.environ.items() if k != ENV_VAR}
        if shell_value is not None:
            env[ENV_VAR] = shell_value
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([str(py), "-c", script, "--out", tmp] + args, env=env, capture_output=True, text=True, timeout=120, cwd=ROOT)
        assert p.returncode == 0 and f"ENV={expect}" in p.stdout, (args, shell_value, p.stdout, p.stderr[-800:])


if __name__ == "__main__":
    import time
    for name, fn in sorted((n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)):
        t0 = time.time()
        fn()
        print(f"ok {name} ({time.time() - t0:.1f}s)")
    print("OK: publish gate (golden side): PUBLISHED read from source, unpublished native class needs no snapshot, run_all env propagation, gen_fixtures flag")
