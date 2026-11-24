"""Which skill-level growth mode a test module runs in (``engine.common.factors``: the LEGACY 300-clamp of the frozen workbooks vs the EXTENDED linear curves).

Every module that compares the engine with a WORKBOOK-derived golden (``<class>_golden.json`` / ``_artifacts_golden`` / ``_sensitivity_golden`` / cubes / equipment / potentials, made from Excel or
the verify scripts, which clamp at level 300) calls ``pin("legacy")`` at import - so it is pinned however it is started (run_all, by hand, pytest).  The ENGINE-NATIVE classes
(no workbook; their snapshots and checks are made in production mode) and the factor tests call ``pin("extended")``.  A module exposes the returned string as ``FACTOR_MODE`` so the
autouse fixture of ``conftest.py`` can re-apply it per test when several modules share one pytest session.  Production never sets legacy mode.
"""
import functools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.common import factors  # noqa: E402

LEGACY, EXTENDED = "legacy", "extended"


def pin(mode):
    """Switch this process to ``mode`` ("legacy" | "extended"); returns the mode name (for ``FACTOR_MODE = pin(...)``)."""
    assert mode in (LEGACY, EXTENDED), mode
    factors.set_legacy_clamp(mode == LEGACY)
    return mode


def scope(native):
    """Context manager: extended for an engine-native class, legacy for a workbook class (update_goldens)."""
    return factors.legacy_clamp(not native)


def legacy_scoped(fn):
    """Decorator: run ``fn`` in legacy mode and restore the previous mode afterwards (the workbook comparers shared with the engine-native tests)."""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        with factors.legacy_clamp(True):
            return fn(*a, **kw)
    return wrapper
