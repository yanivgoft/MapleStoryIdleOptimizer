#!/usr/bin/env python3
"""One-command regression run for the whole app (engine goldens, API tests, web tests) - no agent needed, output kept tiny.

    python3 tests/run_all.py                  # everything (golden jobs + API pytest + web vitest/tsc/xlsx-map check)
    python3 tests/run_all.py --changed        # only what the uncommitted changes (git status) can affect
    python3 tests/run_all.py --only golden    # golden | api | web  (repeatable)
    python3 tests/run_all.py --class hero     # one class: its goldens + API tests (-k) ; implies --only golden --only api
    python3 tests/run_all.py --build          # also `npm run build`
    python3 tests/run_all.py -v               # also list every passing suite with its time

Output: one line per group + a verdict line; for a failure only the last lines of that suite's output (``--tail N``, default 25).
Exit code 0 = everything green, 1 = a failure, 2 = environment problem (wrong Python / missing tool).

Golden jobs come from ``tests/golden/registry.py``: per class its class golden (``test_<id>.py``), ``test_artifacts.py --class <id>`` and
``test_sensitivity.py --class <id>`` (three jobs, run in parallel like the old per-class scripts), plus every global ``test_*.py`` (cubes, equipment, potentials,
artifact five-slots).  ``--class <id>`` selects that class's three jobs.  An ENGINE-NATIVE class (every ``engine/classes/<id>.py`` without a workbook, e.g. dawn_warrior) has
``test_snapshots.py --class <id>`` + ``test_engine_native.py --class <id>`` instead (plus its own ``test_<id>_*.py`` scripts, run once in a full run and under ``--class <id>``);
``--class <id>`` also selects the API tests whose name contains the id.  An UNPUBLISHED native class (module exports ``PUBLISHED = False``) needs no snapshot: its snapshot job is
skipped with a printed note until the file exists.  Every subprocess gets ``MSI_INCLUDE_UNPUBLISHED=1`` (``child_env``) so the API registry serves such classes to the tests.

The golden scripts compare the engine to the workbooks' verify scripts bit-exactly and need Python 3.11 with PYTHONHASHSEED=0 (3.12 changes sum() rounding);
this runner sets the seed itself and refuses to run on another Python minor version (override: --allow-any-python).  Golden scripts read only JSON files, so they
run in parallel (--jobs, default min(4, CPUs)); the slow `formulas`-package evaluations are NOT part of this (they are how the goldens were generated).
"""
import argparse
import concurrent.futures as cf
import glob
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_DIR = os.path.join(ROOT, "tests", "golden")
sys.path.insert(0, GOLDEN_DIR)
import registry  # noqa: E402  (tests/golden/registry.py: the one list of classes + their golden jobs)

CLASSES = list(registry.ALL)             # the 12 workbook classes + the engine-native ones (every other engine/classes/<id>.py)
SLOW_FIRST = ("test_cubes.py",)          # start the longest script first so the pool finishes sooner


def child_env(extra=None, base=None):
    """The environment of EVERY subprocess run_all starts (golden jobs, API pytest, web group, git): PYTHONHASHSEED=0 (the goldens' set-order sums) and
    ``MSI_INCLUDE_UNPUBLISHED=1`` so a class that exports ``PUBLISHED = False`` (under development, hidden on the live site) is still served by the API registry and tested."""
    e = dict(os.environ if base is None else base, PYTHONHASHSEED="0", MSI_INCLUDE_UNPUBLISHED="1")
    e.update(extra or {})
    return e


def run(cmd, cwd=ROOT, env=None, timeout=1800):
    """(returncode, combined output, seconds)."""
    t0 = time.time()
    e = child_env(env)
    try:
        p = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t0
    except subprocess.TimeoutExpired as ex:
        return 124, f"TIMEOUT after {timeout}s\n{(ex.stdout or b'')[-2000:]}", time.time() - t0
    except FileNotFoundError as ex:
        return 127, f"command not found: {ex}", time.time() - t0


def changed_groups():
    """Groups touched by `git status` (uncommitted + untracked): web/ -> web; engine/api/src/tests/data -> golden + api; nothing relevant -> none."""
    rc, out, _ = run(["git", "status", "--porcelain"])
    if rc != 0:
        return {"golden", "api", "web"}
    paths = [ln[3:].split(" -> ")[-1].strip().strip('"') for ln in out.splitlines() if ln.strip()]
    groups = set()
    for p in paths:
        if p.startswith("web/"):
            groups.add("web")
        elif p.startswith(("engine/", "api/", "src/", "tests/", "data/")):
            groups.update(("golden", "api"))
        elif p.endswith(".xlsx") or p.startswith(".github/"):
            groups.update(("golden", "api"))     # a workbook / the CI file: cheap enough to be safe
    return groups


def golden_jobs(cls=None):
    """[(label, [script path, args...])]: the registry's jobs (per class: class golden, artifacts, sensitivity; ``cls`` selects one class) plus the global scripts
    (test_cubes ... - not with ``cls``); the slow script first."""
    jobs = [(label, [os.path.join(GOLDEN_DIR, argv[0])] + argv[1:]) for label, argv in registry.all_jobs(cls)]
    jobs.sort(key=lambda j: os.path.basename(j[1][0]) not in SLOW_FIRST)       # (stable: otherwise the registry's order)
    return jobs


def api_python():
    venv = os.path.join(ROOT, ".venv", "bin", "python")
    return venv if os.path.exists(venv) else sys.executable


def last_line(text):
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def run_golden(args, results):
    jobs = golden_jobs(args.cls)
    for label, note in registry.skipped_jobs():
        if not args.cls or label.split(":")[0] == args.cls:
            print(f"note: {label} skipped ({note})")
    if not jobs:
        results.append(("golden", False, f"no golden jobs match --class {args.cls}", []))
        return
    fails, passed = [], 0
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = {pool.submit(run, [sys.executable] + cmd): label for label, cmd in jobs}
        for f in cf.as_completed(futs):
            rc, out, secs = f.result()
            name = futs[f]
            if rc == 0:
                passed += 1
                if args.verbose:
                    print(f"  ok  {name} ({secs:.0f}s)  {last_line(out)[:110]}")
            else:
                fails.append((name, out))
    ok = not fails
    detail = [f"--- {n} (exit != 0), last {args.tail} lines:\n" + "\n".join(o.strip().splitlines()[-args.tail:]) for n, o in sorted(fails)]
    results.append(("golden", ok, f"{passed}/{len(jobs)} golden jobs ok in {time.time() - t0:.0f}s" + ("" if ok else f"; FAILED: {', '.join(n for n, _ in sorted(fails))}"), detail))


def run_api(args, results):
    """pytest api/tests split into ``--api-jobs`` processes (files dealt out largest-first; no xdist needed)."""
    files = sorted(glob.glob(os.path.join(ROOT, "api", "tests", "test_*.py")), key=os.path.getsize, reverse=True)
    n = max(1, min(args.api_jobs, len(files)))
    chunks = [files[i::n] for i in range(n)]
    base = [api_python(), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", "-W", "ignore"]
    if args.fail_fast:
        base.append("-x")
    if args.cls:
        base += ["-k", args.cls]
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=n) as pool:
        outs = list(pool.map(lambda c: run(base + [os.path.relpath(f, ROOT) for f in c]), chunks))
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "deselected": 0}
    for rc, out, _ in outs:
        for k in counts:
            m = re.search(rf"\b(\d+) {k}", out)
            if m:
                counts[k] += int(m.group(1))
    bad = [(rc, out) for rc, out, _ in outs if rc not in (0, 5)]          # 5 = a chunk with no test left after -k
    if counts["passed"] == 0 and not bad:
        results.append(("api", False, f"no API tests match --class {args.cls}", []))
        return
    summary = ", ".join(f"{v} {k}" for k, v in counts.items() if v and k != "deselected")
    detail = ["--- pytest, last %d lines:\n" % args.tail + "\n".join(out.strip().splitlines()[-args.tail:]) for _, out in bad]
    results.append(("api", not bad, f"{summary} in {time.time() - t0:.0f}s", detail))


def run_web(args, results):
    web = os.path.join(ROOT, "web")
    if not shutil.which("npx") or not os.path.isdir(os.path.join(web, "node_modules")):
        results.append(("web", False, "npx / web/node_modules missing: run `cd web && npm install` (or skip with --only golden --only api)", []))
        return
    steps = [("vitest", ["npx", "vitest", "run"]), ("tsc", ["npx", "tsc", "--noEmit"]),
             ("xlsx-map", [sys.executable, "web/scripts/gen_xlsx_map.py", "--check"])]
    if args.build:
        steps.append(("build", ["npm", "run", "build"]))
    parts, detail, ok = [], [], True
    t0 = time.time()
    for name, cmd in steps:
        rc, out, secs = run(cmd, cwd=web if cmd[0] in ("npx", "npm") else ROOT)
        if rc == 0:
            m = re.search(r"Tests\s+(\d+) passed", out) if name == "vitest" else None
            parts.append(f"{name} ok" + (f" ({m.group(1)} tests)" if m else ""))
        else:
            ok = False
            parts.append(f"{name} FAILED")
            detail.append(f"--- {name}, last {args.tail} lines:\n" + "\n".join(out.strip().splitlines()[-args.tail:]))
    results.append(("web", ok, ", ".join(parts) + f" in {time.time() - t0:.0f}s", detail))


def main():
    ap = argparse.ArgumentParser(description="One-command regression run (see the module docstring).")
    ap.add_argument("--only", action="append", choices=["golden", "api", "web"], help="run only this group (repeatable)")
    ap.add_argument("--class", dest="cls", choices=CLASSES, help="one class: its goldens + API tests")
    ap.add_argument("--changed", action="store_true", help="only the groups the uncommitted changes can affect")
    ap.add_argument("--build", action="store_true", help="also npm run build")
    ap.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 2))
    ap.add_argument("--api-jobs", type=int, default=min(4, os.cpu_count() or 2), help="parallel pytest processes for api/tests")
    ap.add_argument("--max-details", type=int, default=3, help="how many failing suites' output tails to print")
    ap.add_argument("--tail", type=int, default=25, help="lines of a failing suite's output to print")
    ap.add_argument("-x", "--fail-fast", action="store_true", help="API tests: stop at the first failure")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--allow-any-python", action="store_true")
    args = ap.parse_args()

    if sys.version_info[:2] != (3, 11) and not args.allow_any_python:
        print(f"ENV: need Python 3.11 (this is {sys.version_info.major}.{sys.version_info.minor}): the goldens depend on 3.11's sum() rounding. "
              "Use /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 tests/run_all.py (or --allow-any-python).")
        return 2

    groups = set(args.only or ["golden", "api", "web"])
    if args.cls and not args.only:
        groups = {"golden", "api"}
    if args.changed:
        groups &= changed_groups()
        if not groups:
            print("NOTHING TO RUN: the uncommitted changes touch no engine / api / src / tests / data / web files.")
            return 0

    results = []
    t0 = time.time()
    # golden runs in its own thread pool; api + web run in parallel with it (they are independent processes)
    runners = {"golden": run_golden, "api": run_api, "web": run_web}
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        for f in [pool.submit(runners[g], args, results) for g in ("golden", "api", "web") if g in groups]:
            f.result()

    order = {"golden": 0, "api": 1, "web": 2}
    for name, ok, summary, _ in sorted(results, key=lambda r: order[r[0]]):
        print(f"{'PASS' if ok else 'FAIL'} {name:6s} {summary}")
    bad = [r for r in results if not r[1]]
    shown = [d for _, _, _, detail in bad for d in detail]
    for d in shown[:args.max_details]:
        print(d)
    if len(shown) > args.max_details:
        print(f"... {len(shown) - args.max_details} more failing suite(s) not shown (rerun them alone, e.g. --class <id> or -v)")
    print(f"{'ALL GREEN' if not bad else 'FAILED: ' + ', '.join(r[0] for r in bad)} ({time.time() - t0:.0f}s total)")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
