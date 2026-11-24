"""pytest only: re-apply each test module's ``FACTOR_MODE`` (see ``factor_mode.py``) around its tests, so workbook-golden modules (legacy 300-clamp) and engine-native / factor
modules (extended) can share one pytest session.  Plain ``python3 tests/golden/<script>.py`` runs need nothing: the modules pin the mode at import."""
import pytest

from engine.common import factors


@pytest.fixture(autouse=True)
def _factor_mode(request):
    mode = getattr(request.module, "FACTOR_MODE", None)
    if mode is None:
        yield
        return
    prev = factors.set_legacy_clamp(mode == "legacy")
    try:
        yield
    finally:
        factors.set_legacy_clamp(prev)
